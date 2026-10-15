"""Account-specific evidence gate; unknown fields remain blockers."""
from typing import Literal
from trading_platform.contracts.values import Record, Name, Time, canonical, digest
from pydantic import Field, model_validator

REQUIRED=frozenset(('account_type','symbol_id','tick_grid','volume_grid','candle_basis','session_state',
    'contract_value','commission','currency_conversion','margin','protection_sides','order_types','expiry'))


class Evidence(Record):
    field: Name
    value: str
    source: Name
    observed_at: Time
    valid_until: Time
    classification: Literal['protocol','demo_observed','broker_verified','synthetic']

    @model_validator(mode='after')
    def check(self):
        if self.valid_until<=self.observed_at: raise ValueError('evidence validity')
        return self


class CapabilityReport(Record):
    account_id: Name
    environment: Literal['demo'] = 'demo'
    symbol: Name
    evidence: tuple[Evidence,...] = ()

    @model_validator(mode='after')
    def unique(self):
        if len({e.field for e in self.evidence})!=len(self.evidence): raise ValueError('duplicate field evidence')
        return self

    def blockers(self, now, account_id, symbol):
        missing=set(REQUIRED)
        if self.account_id!=str(account_id) or self.symbol!=symbol: missing.add('identity')
        for e in self.evidence:
            if e.classification in ('demo_observed','broker_verified') and e.observed_at<=now<e.valid_until and e.value.strip():
                missing.discard(e.field)
        return sorted(missing)

    @property
    def hash(self): return digest(self)
