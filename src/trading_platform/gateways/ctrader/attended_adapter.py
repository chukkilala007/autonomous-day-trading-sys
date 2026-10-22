"""Disabled-by-default attended adapter over the existing qualified transport.

No launcher or approval issuer. Production capability checks are preserved;
this adapter does not turn preparation evidence into execution qualification.
"""
import json
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from twisted.internet import defer
from trading_platform.contracts.orders import Entry, Management
from trading_platform.contracts.values import Record, Name, Positive, Time, canonical, digest, utc
from .valuation import Hash
from .normalization import integer
from .management import send_owned
from .economics import EconomicsCollector


class Approval(Record):
    account_id: Name
    test_id: Name
    proposal_hash: Hash
    review_bundle_hash: Hash
    capability_hash: Hash
    approved_at: Time
    submit_before: Time
    maximum_loss: Positive
    quantity: Literal[1000] = 1000
    scope: Literal['one_entry_and_owned_cancel_close'] = 'one_entry_and_owned_cancel_close'


class Adapter:
    def __init__(self, gateway, binding, ledger, report, approval, *, approved_hash, now, enabled=False):
        approval=Approval.model_validate_json(approval.model_dump_json())
        if digest(approval)!=approved_hash: raise ValueError('approval pin mismatch')
        if not 0<approval.maximum_loss<=5 or not approval.approved_at<approval.submit_before:
            raise ValueError('invalid bounded approval')
        if (gateway.db is not binding.db or ledger.db is not gateway.db
                or gateway.session is not binding.session or ledger.account!=approval.account_id
                or str(gateway.session.account_id)!=approval.account_id):
            raise ValueError('foreign adapter composition')
        if approval.review_bundle_hash!=binding.pin or approval.capability_hash!=digest(report):
            raise ValueError('unapproved evidence')
        self.gateway=gateway;self.binding=binding;self.ledger=ledger;self.now=now
        self.approval=approval;self.approved_hash=approved_hash;self.report=type(report).model_validate_json(report.model_dump_json())
        self.enabled=enabled;self.key='attended-attempt:'+approval.account_id
        self.economics=EconomicsCollector(gateway.session,now)
        self.event_error=False
        gateway.session.client.setMessageReceivedCallback(self.received)

    def received(self, client, message):
        self.binding.received(client,message)
        try:
            from ctrader_open_api import Protobuf
            from google.protobuf.json_format import MessageToDict
            payload=Protobuf.extract(message)
            if payload.DESCRIPTOR.name=='ProtoOAExecutionEvent':
                self.ledger.apply(MessageToDict(payload,preserving_proto_field_name=True))
        except Exception:
            self.event_error=True

    def _check(self):
        s=self.gateway.session
        if (digest(self.approval)!=self.approved_hash or digest(self.report)!=self.approval.capability_hash
                or self.binding.pin!=self.approval.review_bundle_hash):
            raise ValueError('approved evidence changed')
        if not self.enabled or not self.gateway.authorized: raise ValueError('attended submission disabled')
        if self.event_error or not s.ready or s.demo_binding!=dict(account_id=self.approval.account_id,generation=s.generation,is_live=False):
            raise ValueError('authenticated demo session required')
        self.gateway.fence.check(self.binding.core_id,self.binding.epoch)

    @defer.inlineCallbacks
    def submit(self, entry):
        self._check();a=self.approval;now=self.now()
        entry=Entry.model_validate_json(entry.model_dump_json())
        if digest(entry)!=a.proposal_hash or not a.approved_at<=now<a.submit_before:
            raise ValueError('proposal or approval expired/changed')
        if self.gateway.db.connection.execute('SELECT 1 FROM checkpoints WHERE id=?',(self.key,)).fetchone():
            raise ValueError('one attempt consumed; reconcile without resend')
        preview=yield self.binding.preview(entry)
        self._check();now=self.now()
        if (preview['status']!='PREPARED_NOT_AUTHORIZED' or preview['blockers']
                or not preview['created_at']<=now<preview['valid_until']
                or not a.approved_at<=now<a.submit_before
                or preview['planned_loss']>a.maximum_loss or preview['quantity']!=1000):
            raise ValueError('fresh approved preview required')
        command=dict(id=digest(dict(approval=a,entry=entry)),instance=a.test_id,
            body=dict(decision=dict(environment='demo',proposal=json.loads(entry.model_dump_json())),
                      size=dict(quantity='1000')))
        from trading_platform.contracts.events import Quote
        bound_quote=self.binding._quote(now)
        quote=Quote(instrument='EURUSD',bid=bound_quote.bid,ask=bound_quote.ask,
                    source_time=bound_quote.observed_at,received_at=now)
        # Binding already checks original quote/account times. Recheck its short
        # validity before invoking the independent existing capability gate.
        self.gateway.prepare(command,self.binding.core_id,self.binding.epoch,self.report,quote,now,preview['account_observed_at'])
        with self.gateway.db.transaction() as c:
            self._check()
            if c.execute('SELECT 1 FROM checkpoints WHERE id=?',(self.key,)).fetchone():
                raise ValueError('one attempt consumed')
            c.execute('INSERT INTO checkpoints VALUES (?,?)',(self.key,canonical(dict(
                approval_hash=digest(a),command_id=command['id'],owner=a.test_id,at=now,
                status='UNKNOWN_UNTIL_RECONCILED',preview_hash=preview['preview_hash']))))
        # Both this account-wide consumption and the transport's UNKNOWN record
        # survive timeouts/crashes. Even failure before send never permits retry.
        response=yield defer.maybeDeferred(self.gateway.send,command,self.binding.core_id,
            self.binding.epoch,self.report,quote,now,preview['account_observed_at'])
        return dict(status='AWAITING_RECONCILIATION',command_id=command['id'],response_received=response is not None)

    @defer.inlineCallbacks
    def manage(self, action, target_id):
        self._check()
        if action not in ('cancel','close'): raise ValueError('only owned risk-reducing cleanup allowed')
        row=self.gateway.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(self.key,)).fetchone()
        if not row or json.loads(row['body'])['approval_hash']!=digest(self.approval):
            raise ValueError('no matching consumed test approval')
        attempt=json.loads(row['body']);s=self.gateway.session;generation=s.generation
        economics=yield self.economics.collect()
        self._check();now=self.now()
        if generation!=s.generation: raise ValueError('management connection changed')
        if not 0<=(now-utc(economics['observed_at'])).total_seconds()<=2:
            raise ValueError('stale management reconciliation')
        target=(self.ledger.owned_order if action=='cancel' else self.ledger.owned)(target_id,self.approval.test_id)
        current=economics['reconciliation'].get('order' if action=='cancel' else 'position',[])
        id_field='orderId' if action=='cancel' else 'positionId'
        matches=[r for r in current if str(r[id_field])==str(target_id)]
        if len(matches)!=1 or digest(matches[0])!=digest(target['record']):
            raise ValueError('ledger target differs from current broker reconciliation')
        send=self.gateway.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('gateway-send:'+attempt['command_id'],)).fetchone()
        if not send: raise ValueError('no durable original submission')
        original=json.loads(send['body']);expected=original['fields'];raw=matches[0]
        oid=original.get('broker_order_id')
        if not oid or original['instance']!=self.approval.test_id:
            raise ValueError('original order association unknown')
        if action=='cancel' and str(target_id)!=str(oid):
            raise ValueError('cleanup is not original test order')
        if action=='close':
            order=self.gateway.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('broker-order:'+str(oid),)).fetchone()
            if not order or str(json.loads(order['body'])['record'].get('positionId'))!=str(target_id):
                raise ValueError('cleanup is not original test position')
        if integer(raw['tradeData']['symbolId'])!=expected['symbolId']:
            raise ValueError('foreign cleanup symbol')
        quantity=Decimal(target.get('remaining') if action=='cancel' else target['quantity'])
        if not 0<quantity<=1000: raise ValueError('cleanup quantity exceeds bounded test')
        management=Management(target_id=str(target_id),owner=self.approval.test_id,
            revision=target['updated'],action=action,expires_at=now+timedelta(seconds=2))
        command_id=digest(dict(approval=self.approval,action=action,target=str(target_id)))
        yield defer.maybeDeferred(send_owned,self.gateway,self.ledger,command_id,self.approval.test_id,
                                 management,self.binding.core_id,self.binding.epoch,now)
        return dict(status='CLEANUP_UNCONFIRMED',command_id=command_id)
