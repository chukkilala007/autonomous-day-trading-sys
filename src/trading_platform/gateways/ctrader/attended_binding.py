"""Read-only first-test preview from trusted in-process broker components.

Trust root is a deployment-pinned reviewed bundle, not an API caller's hashes.
The bundle is not broker-signed. No default real-account bundle is supplied.
"""
import json
from datetime import timedelta
from typing import Literal
from twisted.internet import defer
from ctrader_open_api import Protobuf
from google.protobuf.json_format import MessageToDict
from trading_platform.contracts.values import Record, digest, canonical, utc
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.events import Quote as FeedQuote
from trading_platform.execution.attended_preview import Quote, Preconditions, prepare
from .valuation import Valuation, Hash
from .contract_builder import Policy, build
from .economics import EconomicsCollector
from .normalization import integer, units
from .read_only_session import ReadOnlySession
from .orders import Fence


class ReviewedBundle(Record):
    policy: Policy
    source_hash: Hash
    image_digest: Hash
    price_grid_review: Hash
    protection_review: Hash
    costs_review: Hash
    entry_expiry_review: Hash
    profile: Literal['EURUSD_USD_absolute_protected_buy_limit_gtd']


class Binding:
    """Owns the session message callback; do not share with another lifecycle.

    Only proposal prices enter preview(). Quotes, valuation, profile, readiness,
    margin and fence checks are obtained here. Intended for an empty first-test
    ledger: any prior commands/intents/reservations/positions require a separate
    recovery workflow, never an optimistic 'already resolved' assertion.
    """
    def __init__(self, session, stream, db, bundle, *, approved_bundle_hash, core_id, epoch, now):
        if not isinstance(session, ReadOnlySession):
            raise ValueError('read-only session required')
        bundle=ReviewedBundle.model_validate_json(bundle.model_dump_json())
        if digest(bundle)!=approved_bundle_hash:
            raise ValueError('reviewed bundle does not match deployment pin')
        p=bundle.policy
        if (p.account_id!=str(session.account_id) or p.instrument!='EURUSD'
                or p.currency!='USD' or p.quote_currency!='USD' or p.contract_value_per_unit!=1):
            raise ValueError('unsupported bound account/contract')
        if stream.session is not session or stream.feed.db is not db or stream.symbols.get('EURUSD')!=p.symbol_id:
            raise ValueError('foreign stream or storage')
        self.session=session; self.stream=stream; self.db=db; self.now=now
        self._bundle_json=bundle.model_dump_json(); self.pin=approved_bundle_hash
        self.core_id=core_id; self.epoch=epoch; self.fence=Fence(db,session.account_id)
        self.economics=EconomicsCollector(session,now); self.revision=0; self.busy=False
        self.failed_event=False
        session.client.setMessageReceivedCallback(self.received)

    def received(self, _client, message):
        try:
            payload=Protobuf.extract(message)
            name=payload.DESCRIPTOR.name
            if name=='ProtoOASpotEvent':
                self.stream.on_spot(MessageToDict(payload,preserving_proto_field_name=True))
            elif name.endswith('Event'):
                self.revision+=1
                self.failed_event=True
                self.stream.disconnected()
        except Exception:
            self.revision+=1; self.failed_event=True; self.stream.disconnected()

    def _state(self):
        s=self.session
        if (not s.ready or s.demo_binding!=dict(account_id=str(s.account_id),generation=s.generation,is_live=False)
                or self.failed_event):
            raise ValueError('authenticated demo generation or reconciliation invalid')
        self.fence.check(self.core_id,self.epoch)
        if self.stream.subscribed_generation!=s.generation:
            raise ValueError('stream generation not repaired')
        # Deliberately conservative: this adapter cannot declare historical commands settled.
        for table in ('commands','positions','reservations','attempts','halts'):
            if self.db.connection.execute('SELECT 1 FROM '+table+' LIMIT 1').fetchone():
                raise ValueError('first-test ledger not empty; recovery required')
        if self.db.connection.execute("SELECT 1 FROM checkpoints WHERE id LIKE 'gateway-send:%' OR id LIKE 'gateway-management:%' OR id LIKE 'broker-position:%' OR id LIKE 'broker-order:%' LIMIT 1").fetchone():
            raise ValueError('prior broker intent or exposure requires recovery')
        return (s.generation,self.revision,self.core_id,self.epoch)

    def _quote(self, now):
        feed=self.stream.feed
        if (feed.get('quote-valid:EURUSD')!={'valid':True}
                or not (feed.get('coverage:EURUSD') or {}).get('repaired')
                or (feed.get('quote-buffer-pending:EURUSD') or {}).get('pending')
                or self.stream.failures):
            raise ValueError('invalid or unrepaired quote')
        q=FeedQuote.model_validate_json(json.dumps(feed.get('quote:EURUSD')))
        if q.instrument!='EURUSD' or q.received_at>now or not 0<=(now-q.source_time).total_seconds()<2:
            raise ValueError('stale or foreign feed quote')
        return Quote(account_id=str(self.session.account_id),instrument='EURUSD',observed_at=q.source_time,
                     bid=q.bid,ask=q.ask,evidence_hash=digest(q))

    @defer.inlineCallbacks
    def preview(self, entry):
        if self.busy: raise ValueError('preview collection already running')
        self.busy=True
        try:
            entry=Entry.model_validate_json(entry.model_dump_json())
            bundle=ReviewedBundle.model_validate_json(self._bundle_json);p=bundle.policy
            if digest(bundle)!=self.pin: raise ValueError('deployment review pin changed')
            state=self._state(); start=self.now()
            created=entry.expires_at-timedelta(seconds=60)
            if not 0<=(start-created).total_seconds()<=10: raise ValueError('proposal creation window')
            if not p.observed_at<=start<p.valid_until: raise ValueError('reviewed policy expired')
            symbols=yield self.session.read('ProtoOASymbolsListReq')
            candidates=[r for r in symbols.get('symbol',[]) if r.get('symbolName')=='EURUSD']
            if (str(symbols.get('ctidTraderAccountId'))!=p.account_id or len(candidates)!=1
                    or integer(candidates[0]['symbolId'])!=p.symbol_id):
                raise ValueError('broker symbol mapping mismatch')
            metadata=yield self.session.read('ProtoOASymbolByIdReq',symbolId=[p.symbol_id])
            rows=metadata.get('symbol',[])
            if (str(metadata.get('ctidTraderAccountId'))!=p.account_id or len(rows)!=1
                    or integer(rows[0]['symbolId'])!=p.symbol_id):
                raise ValueError('foreign symbol metadata')
            raw=rows[0]
            if raw.get('tradingMode')!='ENABLED': raise ValueError('symbol disabled')
            if raw.get('distanceSetIn')!='SYMBOL_DISTANCE_IN_POINTS' or any(integer(raw[k])!=0 for k in ('slDistance','tpDistance')):
                raise ValueError('unsupported protection distance profile')
            for field,wire in [('minimum','minVolume'),('maximum','maxVolume'),('step','stepVolume')]:
                if getattr(p,field)!=units(raw[wire]): raise ValueError('policy volume grid changed')
            # Collect time-sensitive reads concurrently; EconomicsCollector brackets changes.
            margin_at=self.now()
            economics,margin=yield defer.gatherResults([
                self.economics.collect(),
                self.session.read('ProtoOAExpectedMarginReq',symbolId=p.symbol_id,volume=[100000])],consumeErrors=True)
            margin=dict(ctidTraderAccountId=integer(margin['ctidTraderAccountId']),
                moneyDigits=integer(margin['moneyDigits']),margin=[{k:integer(r[k]) for k in
                ('volume','buyMargin','sellMargin')} for r in margin['margin']])
            now=self.now()
            if self._state()!=state: raise ValueError('session/event/fence changed during collection')
            trader=economics['trader'];current=economics['reconciliation']
            if (trader.get('brokerName')!='FxPro' or trader.get('accessRights')!='FULL_ACCESS'
                    or trader.get('isLimitedRisk') is not False):
                raise ValueError('unsupported broker account profile')
            if 'order' not in current or 'position' not in current:
                # Protobuf omits empty repeated fields: the correlated reconcile response
                # is complete by protocol; absence is an empty list here, not history proof.
                current=dict(current,order=current.get('order',[]),position=current.get('position',[]))
            if current['order'] or current['position']: raise ValueError('broker exposure not flat')
            q=self._quote(now)
            contract=build(p,entry,account=self.session.account_id,now=now,quote_to_account='1',
                conversion_observed_at=utc(economics['observed_at']),
                conversion_evidence_hash=digest({'currency':economics['account']['currency'],'quote_currency':p.quote_currency}),
                margin_request=dict(ctidTraderAccountId=self.session.account_id,symbolId=p.symbol_id,volume=[100000]),
                margin_response=margin,margin_observed_at=margin_at)
            v=Valuation.model_validate_json(canonical(dict(mode='demo',account_id=p.account_id,
                observed_at=economics['observed_at'],classification='demo_observed',evidence_hash=economics['evidence_hash'],
                **economics['account'],history_complete=True,external_exposure=False,contracts={'EURUSD':contract})))
            pre=Preconditions(account_id=p.account_id,is_live=False,observed_at=utc(economics['observed_at']),
                valid_until=p.valid_until,proposal_hash=digest(entry),account_profile_review=digest([trader,metadata,symbols]),
                price_grid_review=bundle.price_grid_review,protection_review=bundle.protection_review,
                costs_review=bundle.costs_review,entry_expiry_review=bundle.entry_expiry_review,
                source_hash=bundle.source_hash,image_digest=bundle.image_digest,policy_hash=digest(p),
                reconciled_flat=True,unresolved_commands=0,writer_fenced=True,connected=True)
            # Never roll an existing proposal expiry forward after network latency.
            result=prepare(entry,q,v,pre,now,proposal_created_at=entry.expires_at-timedelta(seconds=60))
            return result
        finally:
            self.busy=False
