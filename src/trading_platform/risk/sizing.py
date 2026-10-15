"""Linear stop-risk model. Unsupported/unknown contract costs fail closed."""
from decimal import Decimal,ROUND_FLOOR
from typing import Literal
from pydantic import Field,model_validator
from trading_platform.contracts.values import Record,Positive,Number,Time,Name


class Contract(Record):
    instrument: Name
    account_currency: Name
    valuation_currency: Name
    quote_to_account: Positive
    contract_value_per_unit: Positive
    commission_per_unit: Number = Field(ge=0)
    slippage_per_unit: Number = Field(ge=0)
    minimum: Positive
    maximum: Positive
    step: Positive
    tick: Positive
    margin_per_unit: Number = Field(ge=0)
    verified_at: Time
    provenance: Name
    linear: Literal[True] = True

    @model_validator(mode='after')
    def valid(self):
        if self.maximum<self.minimum: raise ValueError('volume bounds')
        if self.account_currency!=self.valuation_currency: raise ValueError('valuation currency mismatch')
        return self


class Size(Record):
    quantity: Positive
    unit_risk: Positive
    risk: Positive
    margin: Number


def size(entry,contract,budget,*,now,free_margin,equity,reserve_fraction):
    if contract.instrument!=entry.instrument: raise ValueError('contract mismatch')
    age=(now-contract.verified_at).total_seconds()
    if not 0<=age<=30: raise ValueError('stale valuation')
    if entry.basis!='executable': raise ValueError('research geometry cannot be sized')
    for value in (entry.worst_fill,entry.stop,entry.target,entry.entry,entry.limit):
        if value is not None and value % contract.tick: raise ValueError('price grid')
    unit=abs(entry.worst_fill-entry.stop)*contract.contract_value_per_unit*contract.quote_to_account+contract.commission_per_unit+contract.slippage_per_unit
    cap=min(budget/unit,contract.maximum)
    if cap<contract.minimum: raise ValueError('minimum volume exceeds risk budget')
    quantity=contract.minimum+((cap-contract.minimum)/contract.step).to_integral_value(rounding=ROUND_FLOOR)*contract.step
    margin=quantity*contract.margin_per_unit
    if free_margin-margin<equity*reserve_fraction: raise ValueError('margin reserve')
    return Size(quantity=quantity,unit_risk=unit,risk=quantity*unit,margin=margin)
