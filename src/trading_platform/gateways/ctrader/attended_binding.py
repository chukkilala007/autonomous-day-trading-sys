"""Read-only first-test preview from trusted in-process broker components.

Trust root is a deployment-pinned reviewed bundle, not an API caller's hashes.
The bundle is not broker-signed. No default real-account bundle is supplied.
"""
import json
from datetime import timedelta
from typing import Literal
from pydantic import model_validator
from twisted.internet import defer
from ctrader_open_api import Protobuf
from google.protobuf.json_format import MessageToDict
from trading_platform.contracts.values import Record, Positive, digest, canonical, utc
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.events import Quote as FeedQuote
from trading_platform.execution.attended_preview import Quote, Preconditions, prepare
from .valuation import Valuation, Hash
from .contract_builder import Policy, build
from .economics import EconomicsCollector
from .normalization import integer, units, wire_volume
from .read_only_session import ReadOnlySession
from .orders import Fence
from .broker_profile import BrokerProfile, demo_identity
from .operation_plan import plan
from .modeled_risk import DemoRiskPolicy, prepare as prepare_modeled


class ReviewedBundle(Record):
    policy: Policy | DemoRiskPolicy
    source_hash: Hash
    image_digest: Hash
    price_grid_review: Hash
    protection_review: Hash
    costs_review: Hash
    entry_expiry_review: Hash
    profile: Literal['EURUSD_USD_absolute_protected_buy_limit_gtd', 'USD_linear_absolute_protected_buy_limit_gtd']
    quantity: Positive = '1000'
    contract_value_review: Hash | None = None
    broker_profile: BrokerProfile | None = None
    broker_profile_hash: Hash | None = None

    @model_validator(mode='after')
    def bounded_profile(self):
        if isinstance(self.policy,DemoRiskPolicy) and (self.broker_profile is None or self.quantity!=self.policy.minimum):
            raise ValueError('modeled demo requires broker profile and minimum quantity')
        if self.profile == 'EURUSD_USD_absolute_protected_buy_limit_gtd':
            if self.policy.instrument != 'EURUSD' or self.quantity != 1000 or self.policy.contract_value_per_unit != 1:
                raise ValueError('legacy EURUSD profile changed')
        elif self.contract_value_review is None or 'quantity' not in self.model_fields_set:
            raise ValueError('explicit quantity and contract value review required')
        if (self.broker_profile is None) != (self.broker_profile_hash is None):
            raise ValueError('profile and independent profile pin required together')
        if self.broker_profile is not None:
            bp=self.broker_profile; p=self.policy
            if (digest(bp)!=self.broker_profile_hash or bp.identity.environment!='demo'
                    or bp.identity.account_id!=p.account_id or bp.identity.currency!=p.currency
                    or bp.identity.account_type!='HEDGED'):
                raise ValueError('broker profile/policy identity mismatch')
            matches=[m for m in bp.symbols if m.instrument==p.instrument]
            if len(matches)!=1 or any(getattr(matches[0],k)!=getattr(p,k) for k in
                    ('symbol_id','quote_currency','tick','minimum','maximum','step','contract_value_per_unit')):
                raise ValueError('broker profile/policy contract mismatch')
        wire_volume(self.quantity)
        if not self.policy.minimum <= self.quantity <= self.policy.maximum or (self.quantity-self.policy.minimum) % self.policy.step:
            raise ValueError('reviewed quantity outside contract grid')
        return self


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
        if (p.account_id!=str(session.account_id)
                or p.currency!='USD' or p.quote_currency!='USD'):
            raise ValueError('unsupported bound account/contract')
        if stream.session is not session or stream.feed.db is not db or stream.symbols.get(p.instrument)!=p.symbol_id:
            raise ValueError('foreign stream or storage')
        self.symbol=p.instrument
        self.session=session; self.stream=stream; self.db=db; self.now=now
        self._bundle_json=bundle.model_dump_json(); self.pin=approved_bundle_hash
        self.core_id=core_id; self.epoch=epoch; self.fence=Fence(db,session.account_id)
        self.economics=EconomicsCollector(session,now); self.revision=0; self.busy=False
        self.failed_event=False; self._preview_lease=None
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
        if (feed.get('quote-valid:'+self.symbol)!={'valid':True}
                or not (feed.get('coverage:'+self.symbol) or {}).get('repaired')
                or (feed.get('quote-buffer-pending:'+self.symbol) or {}).get('pending')
                or self.stream.failures):
            raise ValueError('invalid or unrepaired quote')
        q=FeedQuote.model_validate_json(json.dumps(feed.get('quote:'+self.symbol)))
        if q.instrument!=self.symbol or q.received_at>now or not 0<=(now-q.source_time).total_seconds()<2:
            raise ValueError('stale or foreign feed quote')
        return Quote(account_id=str(self.session.account_id),instrument=self.symbol,observed_at=q.source_time,
                     bid=q.bid,ask=q.ask,evidence_hash=digest(q))

    @defer.inlineCallbacks
    def preview(self, entry):
        if self.busy: raise ValueError('preview collection already running')
        self.busy=True
        self._preview_lease=None
        try:
            entry=Entry.model_validate_json(entry.model_dump_json())
            bundle=ReviewedBundle.model_validate_json(self._bundle_json);p=bundle.policy
            if digest(bundle)!=self.pin: raise ValueError('deployment review pin changed')
            if entry.instrument!=p.instrument: raise ValueError('foreign proposal symbol')
            state=self._state(); start=self.now()
            created=entry.expires_at-timedelta(seconds=60)
            if not 0<=(start-created).total_seconds()<=10: raise ValueError('proposal creation window')
            if not p.observed_at<=start<p.valid_until: raise ValueError('reviewed policy expired')
            symbols=yield self.session.read('ProtoOASymbolsListReq')
            native=p.instrument if bundle.broker_profile is None else next(m.native_symbol for m in bundle.broker_profile.symbols if m.instrument==p.instrument)
            candidates=[r for r in symbols.get('symbol',[]) if r.get('symbolName')==native]
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
                self.session.read('ProtoOAExpectedMarginReq',symbolId=p.symbol_id,volume=[wire_volume(bundle.quantity)])],consumeErrors=True)
            margin=dict(ctidTraderAccountId=integer(margin['ctidTraderAccountId']),
                moneyDigits=integer(margin['moneyDigits']),margin=[{k:integer(r[k]) for k in
                ('volume','buyMargin','sellMargin')} for r in margin['margin']])
            now=self.now()
            if self._state()!=state: raise ValueError('session/event/fence changed during collection')
            trader=economics['trader'];current=economics['reconciliation']
            if ((bundle.broker_profile is None and trader.get('brokerName')!='FxPro') or trader.get('accessRights')!='FULL_ACCESS'
                    or trader.get('isLimitedRisk') is not False):
                raise ValueError('unsupported broker account profile')
            operation_plan=None
            if bundle.broker_profile is not None:
                actual=demo_identity(economics,account=self.session.account_id,
                                     binding=self.session.demo_binding,generation=self.session.generation)
                bundle.broker_profile.verify(authenticated_identity=actual,
                    approved_hash=bundle.broker_profile_hash,now=now)
                operation_plan=plan(bundle.broker_profile,entry,authenticated_identity=actual,
                                    approved_hash=bundle.broker_profile_hash,now=now)
                if operation_plan['blockers']:
                    raise ValueError('operation capability blocked: '+','.join(operation_plan['blockers']))
                assets=self.economics.assets.get('asset',[])
                quote=[a for a in assets if str(a['assetId'])==str(candidates[0].get('quoteAssetId'))]
                if len(quote)!=1 or quote[0]['name']!=p.quote_currency:
                    raise ValueError('broker quote currency mismatch')
            if 'order' not in current or 'position' not in current:
                # Protobuf omits empty repeated fields: the correlated reconcile response
                # is complete by protocol; absence is an empty list here, not history proof.
                current=dict(current,order=current.get('order',[]),position=current.get('position',[]))
            if current['order'] or current['position']: raise ValueError('broker exposure not flat')
            q=self._quote(now)
            pre=Preconditions(account_id=p.account_id,is_live=False,observed_at=utc(economics['observed_at']),
                valid_until=min(p.valid_until,utc(operation_plan['valid_until'])) if operation_plan else p.valid_until,proposal_hash=digest(entry),account_profile_review=digest([trader,metadata,symbols]),
                price_grid_review=bundle.price_grid_review,protection_review=bundle.protection_review,
                costs_review=bundle.costs_review,entry_expiry_review=bundle.entry_expiry_review,
                source_hash=bundle.source_hash,image_digest=bundle.image_digest,policy_hash=digest(p),
                reconciled_flat=True,unresolved_commands=0,writer_fenced=True,connected=True)
            # Never roll an existing proposal expiry forward after network latency.
            if isinstance(p,DemoRiskPolicy):
                result=prepare_modeled(p,entry,q,economics,pre,now,quantity=bundle.quantity,
                    margin_response=margin,margin_observed_at=margin_at)
            else:
                contract=build(p,entry,account=self.session.account_id,now=now,quote_to_account='1',
                    conversion_observed_at=utc(economics['observed_at']),
                    conversion_evidence_hash=digest({'currency':economics['account']['currency'],'quote_currency':p.quote_currency}),
                    margin_request=dict(ctidTraderAccountId=self.session.account_id,symbolId=p.symbol_id,volume=[wire_volume(bundle.quantity)]),
                    margin_response=margin,margin_observed_at=margin_at)
                v=Valuation.model_validate_json(canonical(dict(mode='demo',account_id=p.account_id,
                    observed_at=economics['observed_at'],classification='demo_observed',evidence_hash=economics['evidence_hash'],
                    **economics['account'],history_complete=True,external_exposure=False,contracts={p.instrument:contract})))
                result=prepare(entry,q,v,pre,now,proposal_created_at=entry.expires_at-timedelta(seconds=60), quantity=bundle.quantity)
            if operation_plan is not None: result['operation_plan']=operation_plan
            self._preview_lease=canonical(dict(preview=result,metadata=raw,state=state,proposal_hash=digest(entry),bundle_hash=self.pin))
            return result
        finally:
            self.busy=False
