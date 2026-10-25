"""One attended demo attempt or owned recovery; disabled unless explicitly armed."""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from twisted.internet import defer, task
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import canonical, digest
from trading_platform.market_data.service import Feed
from trading_platform.persistence.database import Database
from .attended_adapter import Adapter, Approval
from .attended_binding import Binding, ReviewedBundle
from .attended_monitor import Monitor
from .auth import TokenStore
from .client import VerifiedClient
from .execution import ExecutionLedger
from .execution_review import protocol_profile
from .first_test import FirstTestTransport, Review
from .launch_preflight import check
from .orders import Fence
from .provider import Provider
from .read_only_session import ReadOnlySession
from .settlement import CostPolicy
from .stream import Stream


def inputs(args, now):
    """Load once, validate independent pins before credentials or storage access."""
    bundle = ReviewedBundle.model_validate_json(Path(args.bundle).read_text())
    entry = Entry.model_validate_json(Path(args.proposal).read_text())
    review = Review.model_validate_json(Path(args.review).read_text())
    approval = Approval.model_validate_json(Path(args.approval).read_text())
    costs = CostPolicy.model_validate_json(Path(args.cost_policy).read_text())
    for value, pin in ((bundle, args.approved_bundle_hash), (review, args.approved_review_hash),
                       (approval, args.approved_approval_hash), (costs, args.approved_cost_policy_hash)):
        if digest(value) != pin:
            raise ValueError('independent pin mismatch')
    if bundle.broker_profile is None:
        raise ValueError('portable broker profile required')
    semantics = bundle.policy.classification
    semantics = 'demo_modeled_risk' if semantics == 'demo_modeled_risk' else 'verified_bound'
    if (bundle.policy.account_id != args.account_id or review.account_id != args.account_id
            or approval.account_id != args.account_id or costs.account_id != args.account_id
            or review.review_bundle_hash != digest(bundle) or approval.review_bundle_hash != digest(bundle)
            or approval.capability_hash != digest(review) or approval.proposal_hash != digest(entry)
            or review.symbol != bundle.policy.instrument or entry.instrument != review.symbol
            or approval.quantity != bundle.quantity or not 0 < approval.maximum_loss <= 5
            or not approval.approved_at < approval.submit_before
            or not review.observed_at < review.valid_until
            or not costs.verified_at < costs.valid_until
            or review.risk_semantics != semantics or approval.risk_semantics != semantics
            or (semantics == 'demo_modeled_risk' and not approval.accepts_unbounded_realized_loss)
            or review.protocol_hash != digest(protocol_profile())):
        raise ValueError('inconsistent launch review')
    if not args.recover:
        report = check(bundle, entry, account_id=args.account_id,
                       approved_bundle_hash=args.approved_bundle_hash, now=now)
        if (report['blockers'] or not approval.approved_at <= now < approval.submit_before
                or not review.observed_at <= now < review.valid_until
                or not costs.verified_at <= now < costs.valid_until):
            raise ValueError('blocked or expired launch inputs')
    # Recovery preserves original pins and allows expired entry approvals. It
    # cannot submit; fresh broker identity, ownership and fencing still apply.
    return SimpleNamespace(bundle=bundle, entry=entry, review=review, approval=approval, costs=costs)


def assemble(session, stream, db, data, args, now, *, spot_buffer=None):
    core = 'attended-first-test'
    epoch = Fence(db, args.account_id).acquire(core)
    binding = Binding(session, stream, db, data.bundle, approved_bundle_hash=args.approved_bundle_hash,
                      core_id=core, epoch=epoch, now=now, spot_buffer=spot_buffer)
    gateway = FirstTestTransport(binding, data.review, approved_review_hash=args.approved_review_hash,
                                 approved_approval_hash=args.approved_approval_hash, authorized=args.execute)
    adapter = Adapter(gateway, binding, ExecutionLedger(db, int(args.account_id)), data.review,
                      data.approval, approved_hash=args.approved_approval_hash, now=now, enabled=args.execute)
    # Monitoring requires observed economics/settlement, not modeled Contracts.
    provider = Provider(session, db, lambda: {}, lambda: data.costs, now)
    collect_economics = provider.economics.collect
    @defer.inlineCallbacks
    def scoped_economics():
        economics = yield collect_economics()
        from .broker_profile import demo_identity
        actual = demo_identity(economics, account=session.account_id,
                               binding=session.demo_binding, generation=session.generation)
        if actual != data.bundle.broker_profile.identity:
            raise ValueError('recovery broker identity mismatch')
        return economics
    provider.economics.collect = scoped_economics
    monitor = Monitor(adapter, provider, now=now, enabled=args.execute)
    return adapter, monitor


@defer.inlineCallbacks
def lifecycle(reactor, session, stream, adapter, monitor, entry, *, recover):
    while not session.ready:
        if session.error:
            raise ValueError('authentication unavailable')
        yield task.deferLater(reactor, .05, lambda: None)
    if recover:
        if monitor._read(adapter.key) is None:
            return dict(status='RECOVERY_REQUIRES_ATTEMPT', exposure_resolved=False)
    else:
        # Check the durable account-wide attempt before feed work; never resend.
        if monitor._read(adapter.key) is not None:
            return dict(status='RECOVERY_REQUIRED', exposure_resolved=False)
        yield stream.repair()
        generation = session.generation
        while True:
            if not session.ready or session.generation != generation or adapter.binding.failed_event:
                raise ValueError('connection changed')
            try:
                adapter.binding._quote(adapter.now())
                break
            except ValueError:
                yield task.deferLater(reactor, .05, lambda: None)
        try:
            yield adapter.submit(entry)
        except defer.CancelledError:
            raise
        except Exception:
            # A lost acknowledgement may follow a durable send. Reconcile it;
            # never retry and never mistake a transport error for no exposure.
            if monitor._read(adapter.key) is None:
                raise
    while True:
        state = yield monitor.tick()
        if state['status'] in ('COMPLETE', 'TERMINAL_UNFILLED_COST_REVIEW_REQUIRED'):
            return dict(status=state['status'], exposure_resolved=state['status'] == 'COMPLETE')
        yield task.deferLater(reactor, 1, lambda: None)


@defer.inlineCallbacks
def run(reactor, args, now=lambda: datetime.now(timezone.utc)):
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    report = dict(status='DISABLED', orders_enabled=False, exposure_resolved=False)
    client = session = db = monitor = adapter = buffer = None
    try:
        if args.execute:
            data = inputs(args, now())
            store = TokenStore(args.credentials, args.tokens)
            store.read()
            db = Database(args.database)
            client = VerifiedClient(reactor)
            session = ReadOnlySession(client, store, args.account_id)
            stream = Stream(session, Feed(db), {data.bundle.policy.instrument:data.bundle.policy.symbol_id}, [], now)
            from .spot_buffer import configured_buffer
            buffer = configured_buffer(stream, reactor, time.monotonic, getattr(args, 'quote_buffer_ms', 0))
            adapter, monitor = assemble(session, stream, db, data, args, now, spot_buffer=buffer)
            def disconnected(*event):
                session.disconnected(*event)
                stream.disconnected()
            client.setDisconnectedCallback(disconnected)
            client.startService()
            report = yield lifecycle(reactor, session, stream, adapter, monitor, data.entry,
                                     recover=args.recover).addTimeout(180, reactor)
    except (defer.TimeoutError, defer.CancelledError):
        report = dict(status='STOPPED_UNCONFIRMED', exposure_resolved=False)
    except Exception:
        report = dict(status='RECONCILIATION_REQUIRED' if adapter else 'INPUT_OR_STARTUP_FAILED',
                      exposure_resolved=False)
    finally:
        # Cancellation retires all write paths before callbacks or storage close.
        if monitor is not None:
            monitor.stop()
        if adapter is not None:
            adapter.enabled = False
            adapter.gateway.authorized = False
        if client is not None:
            client.setMessageReceivedCallback(lambda *_: None)
            client.setConnectedCallback(lambda *_: None)
            client.setDisconnectedCallback(lambda *_: None)
        if buffer is not None:
            report['quote_buffer'] = buffer.report()
            buffer.reset()
        if session is not None:
            if session.authenticated is not None and not session.authenticated.called:
                session.authenticated.cancel()
            session.ready = False
            session.demo_binding = None
        if client is not None:
            try:
                yield defer.maybeDeferred(client.stopService).addTimeout(5, reactor)
            except Exception:
                report = dict(status='CLIENT_STOP_UNCONFIRMED', exposure_resolved=False)
        if db is not None:
            try:
                db.close()
            except Exception:
                report = dict(status='STORAGE_CLOSE_UNCONFIRMED', exposure_resolved=False)
        report['orders_enabled'] = False
        report['activation_requested'] = bool(args.execute)
        report['recovery_only'] = bool(args.recover)
        with os.fdopen(fd, 'w') as output:
            output.write(canonical(report)+'\n')
            output.flush()
            os.fsync(output.fileno())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'proposal', 'review', 'approval', 'cost-policy', 'account-id',
                 'approved-bundle-hash', 'approved-review-hash', 'approved-approval-hash',
                 'approved-cost-policy-hash', 'credentials', 'tokens', 'database', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--quote-buffer-ms', type=int, choices=(0, 100), default=0)
    parser.add_argument('--execute', action='store_true', help='Requires separately authorized, pinned J09 inputs')
    parser.add_argument('--recover', action='store_true', help='Only monitor/manage an existing consumed attempt; never submit')
    args = parser.parse_args()
    @defer.inlineCallbacks
    def execute(reactor):
        pending = run(reactor, args)
        def shutdown():
            pending.cancel()
            return pending
        trigger = reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
        try:
            report = yield pending
        except Exception:
            print(json.dumps(dict(status='REPORT_UNAVAILABLE', orders_enabled=False)))
            raise SystemExit(2)
        finally:
            try:
                reactor.removeSystemEventTrigger(trigger)
            except ValueError:
                pass  # The shutdown trigger may already have fired.
        print(json.dumps(dict(status=report['status'], orders_enabled=False, report_written=True)))
        if report['status'] not in ('DISABLED', 'COMPLETE'):
            raise SystemExit(2)
    task.react(execute)


if __name__ == '__main__':
    main()
