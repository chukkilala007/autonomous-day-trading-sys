"""Read-only proposal economics callback with bounded, revision-aware evidence reuse."""
from twisted.internet import defer
from trading_platform.contracts.values import digest
from .contract_builder import build
from .normalization import integer


class MarginQuote:
    def __init__(self,session,policy,conversion,volumes,revision,now):
        self.session=session;self.policy=policy;self.conversion=conversion
        self.volumes=volumes;self.revision=revision;self.now=now;self.cache={}

    @defer.inlineCallbacks
    def __call__(self,entry):
        if not self.session.ready: raise ValueError('account not ready')
        policy=self.policy(entry.instrument)
        conversion=self.conversion(entry.instrument)
        volumes=list(self.volumes(entry))
        if not 1<=len(volumes)<=1000 or len(set(volumes))!=len(volumes) or any(type(v) is not int or v<=0 for v in volumes):
            raise ValueError('unique bounded raw volume candidates required')
        if policy.account_id!=str(self.session.account_id) or policy.instrument!=entry.instrument:
            raise ValueError('foreign contract policy')
        now=self.now()
        if not policy.observed_at<=now<policy.valid_until or now>=entry.expires_at:
            raise ValueError('expired policy or proposal')
        if conversion['account_id']!=str(self.session.account_id) or conversion['currency']!=policy.currency or conversion['source_currency']!=policy.quote_currency or conversion['instrument']!=entry.instrument:
            raise ValueError('foreign conversion evidence')
        if not 0<=(now-conversion['observed_at']).total_seconds()<=2: raise ValueError('stale conversion')
        state=(self.session.generation,self.revision())
        key=digest(dict(entry=entry,policy=policy,conversion=conversion,volumes=volumes,state=state))
        cached=self.cache.get(key)
        if cached and 0<=(now-cached.exact_costs.observed_at).total_seconds()<=2:
            return cached
        request=dict(ctidTraderAccountId=self.session.account_id,symbolId=policy.symbol_id,volume=volumes)
        raw=yield self.session.read('ProtoOAExpectedMarginReq',symbolId=policy.symbol_id,volume=volumes)
        if not self.session.ready or state!=(self.session.generation,self.revision()):
            raise ValueError('session or exposure changed during margin collection')
        response=dict(ctidTraderAccountId=integer(raw['ctidTraderAccountId']),moneyDigits=integer(raw['moneyDigits']),
            margin=[{k:integer(row[k]) for k in ('volume','buyMargin','sellMargin')} for row in raw['margin']])
        contract=build(policy,entry,account=self.session.account_id,now=self.now(),quote_to_account=conversion['rate'],
            conversion_observed_at=conversion['observed_at'],conversion_evidence_hash=conversion['evidence_hash'],
            margin_request=request,margin_response=response,margin_observed_at=now)
        if len(self.cache)>=128:self.cache.clear()
        self.cache[key]=contract
        return contract
