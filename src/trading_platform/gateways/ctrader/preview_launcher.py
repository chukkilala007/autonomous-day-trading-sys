"""One bounded read-only preview. No submission transport or enable option."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from twisted.internet import defer, task
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import canonical
from trading_platform.market_data.service import Feed
from trading_platform.persistence.database import Database
from .attended_binding import Binding, ReviewedBundle
from .auth import TokenStore
from .client import VerifiedClient
from .launch_preflight import load_check
from .orders import Fence
from .read_only_session import ReadOnlySession
from .stream import Stream


@defer.inlineCallbacks
def collect(reactor, session, stream, binding, entry):
    while not session.ready:
        if session.error:
            raise ValueError('authentication unavailable')
        yield task.deferLater(reactor, .05, lambda: None)
    generation = session.generation
    yield stream.repair()
    while True:
        if not session.ready or session.generation != generation or binding.failed_event:
            raise ValueError('connection changed')
        try:
            binding._quote(binding.now())
            break
        except ValueError:
            yield task.deferLater(reactor, .05, lambda: None)
    # The original Entry expiry is preserved, including time consumed by startup.
    return (yield binding.preview(entry))


@defer.inlineCallbacks
def run(reactor, args, now=lambda: datetime.now(timezone.utc)):
    # Exclusive creation also refuses symlinks/existing output. No secrets accessed yet.
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    report = dict(status='FAILED', reason='READONLY_PREVIEW_FAILED', orders_enabled=False)
    client = db = session = None
    try:
        # Recheck parsed inputs against the pin before assembly.
        preflight = load_check(args.bundle, args.proposal, account_id=args.account_id,
                               approved_bundle_hash=args.approved_bundle_hash, now=now())
        if preflight['blockers']:
            report = preflight
        else:
            bundle = ReviewedBundle.model_validate_json(Path(args.bundle).read_text())
            entry = Entry.model_validate_json(Path(args.proposal).read_text())
            from .launch_preflight import check
            checked = check(bundle, entry, account_id=args.account_id,
                            approved_bundle_hash=args.approved_bundle_hash, now=now())
            if checked['blockers'] or checked['proposal_hash'] != preflight['proposal_hash']:
                raise ValueError('inputs changed')
            store = TokenStore(args.credentials, args.tokens)
            store.read()
            db = Database(args.database)
            client = VerifiedClient(reactor)
            session = ReadOnlySession(client, store, args.account_id)
            feed = Feed(db)
            stream = Stream(session, feed, {bundle.policy.instrument:bundle.policy.symbol_id}, [], now)
            core = 'readonly-preview'
            epoch = Fence(db, args.account_id).acquire(core)
            binding = Binding(session, stream, db, bundle,
                              approved_bundle_hash=args.approved_bundle_hash,
                              core_id=core, epoch=epoch, now=now)
            def disconnected(*event):
                session.disconnected(*event)
                stream.disconnected()
            client.setDisconnectedCallback(disconnected)
            client.startService()
            report = yield collect(reactor, session, stream, binding, entry).addTimeout(30, reactor)
    except defer.TimeoutError:
        report = dict(status='FAILED', reason='PREVIEW_TIMEOUT', orders_enabled=False)
    except Exception:
        # Do not serialize exception text, authentication responses or input contents.
        report = dict(status='FAILED', reason='READONLY_PREVIEW_FAILED', orders_enabled=False)
    finally:
        if client is not None:
            # Retire callbacks before closing storage, even if stop times out.
            client.setMessageReceivedCallback(lambda *_: None)
            client.setConnectedCallback(lambda *_: None)
            client.setDisconnectedCallback(lambda *_: None)
        if session is not None:
            if session.authenticated is not None and not session.authenticated.called:
                session.authenticated.cancel()
            session.ready = False
            session.demo_binding = None
        if client is not None:
            try:
                yield defer.maybeDeferred(client.stopService).addTimeout(5, reactor)
            except Exception:
                report = dict(status='FAILED', reason='CLIENT_STOP_UNCONFIRMED', orders_enabled=False)
        if db is not None:
            try:
                db.close()
            except Exception:
                report = dict(status='FAILED', reason='STORAGE_CLOSE_UNCONFIRMED', orders_enabled=False)
        with os.fdopen(fd, 'w') as output:
            output.write(canonical(report)+'\n')
            output.flush()
            os.fsync(output.fileno())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','proposal','account-id','approved-bundle-hash',
                 'credentials','tokens','database','output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    @defer.inlineCallbacks
    def execute(reactor):
        try:
            report = yield run(reactor, args)
        except Exception:
            print(json.dumps(dict(status='FAILED', reason='PRIVATE_OUTPUT_UNAVAILABLE', orders_enabled=False)))
            raise SystemExit(2)
        print(json.dumps(dict(status=report['status'], orders_enabled=False, report_written=True)))
        if report['status'] != 'PREPARED_NOT_AUTHORIZED':
            raise SystemExit(2)
    task.react(execute)


if __name__ == '__main__':
    main()
