from typing import Literal
from pydantic import model_validator
from .values import Record, Name, Positive, digest


class AccountPolicy(Record):
    alias: Name
    environment: Literal['paper','demo','live']
    currency: str = 'GBP'
    broker_account: str | None = None
    total_risk: Positive = '0.01'
    per_trade: Positive = '0.005'
    daily_loss: Positive = '0.02'
    concentration: Positive = '0.005'
    free_margin_fraction: Positive = '0.5'

    @model_validator(mode='after')
    def limits(self):
        if self.per_trade > self.total_risk or self.total_risk > 1 or self.daily_loss > 1 or self.free_margin_fraction > 1:
            raise ValueError('invalid account limits')
        if self.environment != 'paper' and not self.broker_account:
            raise ValueError('broker account binding required')
        if len(self.currency)!=3 or not self.currency.isupper(): raise ValueError('currency')
        return self


class Instance(Record):
    schema_version: Literal[1] = 1
    instance_id: Name
    strategy: Name
    package_digest: Name
    mode: Literal['paper','shadow','demo','live']
    universe: tuple[Name,...]
    account: AccountPolicy
    allocation: Positive
    execution_profile: Name = 'protected'
    risk_profile: Literal['linear_stop'] = 'linear_stop'
    parameters: str = '{}'

    @model_validator(mode='after')
    def mandate(self):
        import json
        if not self.universe or len(set(self.universe))!=len(self.universe): raise ValueError('universe')
        if self.mode != 'shadow' and self.mode != self.account.environment: raise ValueError('environment mismatch')
        if self.allocation > self.account.total_risk: raise ValueError('allocation exceeds account policy')
        if not isinstance(json.loads(self.parameters),dict): raise ValueError('parameters object required')
        return self

    @property
    def hash(self): return digest(self)

    @property
    def submission_enabled(self): return self.mode in ('paper','demo','live')
