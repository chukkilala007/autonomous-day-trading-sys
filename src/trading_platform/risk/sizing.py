"""Linear stop-risk model. Unsupported/unknown contract costs fail closed."""
from decimal import Decimal,ROUND_FLOOR
from typing import Literal
from pydantic import Field,model_validator
from trading_platform.contracts.values import Record,Positive,Number,Time,Name,digest


class QuantityCost(Record):
    quantity: Positive
    # Complete round-trip execution cost upper bound in account currency.
    costs: Number = Field(ge=0)
    margin: Number = Field(ge=0)


class ExactCosts(Record):
    account_id: Name
    proposal_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    evidence_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    observed_at: Time
    rows: tuple[QuantityCost, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def unique(self):
        if len({r.quantity for r in self.rows}) != len(self.rows):
            raise ValueError('duplicate quantity economics')
        return self


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
    exact_costs: ExactCosts | None = None

    @model_validator(mode='after')
    def valid(self):
        if self.maximum<self.minimum: raise ValueError('volume bounds')
        if self.account_currency!=self.valuation_currency: raise ValueError('valuation currency mismatch')
        if self.exact_costs:
            if self.commission_per_unit or self.slippage_per_unit or self.margin_per_unit:
                raise ValueError('ambiguous exact and per-unit costs')
            for row in self.exact_costs.rows:
                if not self.minimum <= row.quantity <= self.maximum or (row.quantity-self.minimum) % self.step:
                    raise ValueError('quantity economics outside volume grid')
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
    if contract.exact_costs:
        costs=contract.exact_costs
        if costs.proposal_hash!=digest(entry): raise ValueError('quantity economics proposal mismatch')
        if not 0<=(now-costs.observed_at).total_seconds()<=2: raise ValueError('stale quantity economics')
        unit=abs(entry.worst_fill-entry.stop)*contract.contract_value_per_unit*contract.quote_to_account
        eligible=[]
        for row in costs.rows:
            risk=row.quantity*unit+row.costs
            if risk>0 and risk<=budget and free_margin-row.margin>=equity*reserve_fraction:
                eligible.append(Size(quantity=row.quantity,unit_risk=risk/row.quantity,risk=risk,margin=row.margin))
        if not eligible: raise ValueError('no evidenced quantity within risk and margin limits')
        return max(eligible,key=lambda result:result.quantity)
    unit=abs(entry.worst_fill-entry.stop)*contract.contract_value_per_unit*contract.quote_to_account+contract.commission_per_unit+contract.slippage_per_unit
    cap=min(budget/unit,contract.maximum)
    if cap<contract.minimum: raise ValueError('minimum volume exceeds risk budget')
    quantity=contract.minimum+((cap-contract.minimum)/contract.step).to_integral_value(rounding=ROUND_FLOOR)*contract.step
    margin=quantity*contract.margin_per_unit
    if free_margin-margin<equity*reserve_fraction: raise ValueError('margin reserve')
    return Size(quantity=quantity,unit_risk=unit,risk=quantity*unit,margin=margin)
