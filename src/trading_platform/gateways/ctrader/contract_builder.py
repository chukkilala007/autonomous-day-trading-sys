"""Audited proposal-specific contract assembly; no broker access or authorization."""
from typing import Literal
from pydantic import Field, model_validator
from trading_platform.contracts.values import Record, Name, Positive, Number, Time, digest
from trading_platform.risk.sizing import Contract, ExactCosts, QuantityCost
from .costs import expected_margin


class Policy(Record):
    account_id: Name
    instrument: Name
    symbol_id: int = Field(gt=0)
    currency: Name
    tick: Positive
    minimum: Positive
    maximum: Positive
    step: Positive
    contract_value_per_unit: Positive
    # Upper account-currency cost bounds, including all fee incidences and slippage.
    roundtrip_cost_per_unit: Number = Field(ge=0)
    minimum_total_cost: Number = Field(ge=0)
    fixed_cost: Number = Field(ge=0)
    cost_coverage: Literal['complete_roundtrip_upper_bound']
    classification: Literal['broker_verified']
    evidence_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    observed_at: Time
    valid_until: Time

    @model_validator(mode='after')
    def valid(self):
        if self.valid_until<=self.observed_at or self.maximum<self.minimum:
            raise ValueError('invalid audited policy')
        return self


def build(policy, entry, *, account, now, quote_to_account, conversion_observed_at,
          conversion_evidence_hash, margin_request, margin_response, margin_observed_at):
    """All policy values must be independently audited; no metadata guessing.

    Margin response must belong to the supplied request via transport correlation.
    Only the request's explicit volume candidates become sizeable quantities.
    """
    policy=Policy.model_validate_json(policy.model_dump_json())
    if policy.account_id!=str(account) or policy.instrument!=entry.instrument:
        raise ValueError('foreign contract policy')
    if not policy.observed_at<=now<policy.valid_until: raise ValueError('expired contract policy')
    if now>=entry.expires_at: raise ValueError('expired proposal')
    if not 0<=(now-conversion_observed_at).total_seconds()<=2: raise ValueError('stale conversion')
    if not isinstance(conversion_evidence_hash,str) or len(conversion_evidence_hash)!=64 or any(c not in '0123456789abcdef' for c in conversion_evidence_hash):
        raise ValueError('conversion evidence required')
    volumes=margin_request['volume']
    if not 1<=len(volumes)<=1000 or any(type(v) is not int or v<=0 for v in volumes):
        raise ValueError('explicit bounded raw volumes required')
    rows=[]
    from decimal import Decimal
    for volume in volumes:
        quantity=Decimal(volume)/100
        margin=expected_margin(margin_response,request=margin_request,account=account,symbol_id=policy.symbol_id,volume=volume,side=entry.side.upper(),observed_at=margin_observed_at,now=now)
        costs=max(quantity*policy.roundtrip_cost_per_unit,policy.minimum_total_cost)+policy.fixed_cost
        rows.append(QuantityCost(quantity=quantity,costs=costs,margin=margin))
    evidence=digest(dict(policy=policy,proposal=entry,conversion=str(quote_to_account),conversion_observed_at=conversion_observed_at,conversion_evidence_hash=conversion_evidence_hash,request=margin_request,response=margin_response,margin_observed_at=margin_observed_at))
    return Contract(instrument=policy.instrument,account_currency=policy.currency,valuation_currency=policy.currency,
        quote_to_account=quote_to_account,contract_value_per_unit=policy.contract_value_per_unit,
        commission_per_unit='0',slippage_per_unit='0',margin_per_unit='0',minimum=policy.minimum,
        maximum=policy.maximum,step=policy.step,tick=policy.tick,verified_at=min(conversion_observed_at,margin_observed_at),
        provenance=policy.evidence_hash,exact_costs=ExactCosts(account_id=str(account),proposal_hash=digest(entry),
        evidence_hash=evidence,observed_at=min(conversion_observed_at,margin_observed_at),rows=tuple(rows)))
