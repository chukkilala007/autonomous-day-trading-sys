"""Demo-only modeled loss; never a broker-verified complete loss bound."""
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from pydantic import Field, model_validator
from trading_platform.contracts.values import Record, Name, Positive, Number, Time, digest, utc, decimal
from trading_platform.contracts.orders import Entry
from .valuation import Hash
from .costs import expected_margin
from .normalization import wire_volume, integer


class DemoRiskPolicy(Record):
    classification: Literal['demo_modeled_risk']
    cost_coverage: Literal['reviewed_fees_plus_explicit_assumptions']
    account_id: Name
    instrument: Name
    symbol_id: int = Field(gt=0)
    currency: Literal['USD']
    quote_currency: Literal['USD']
    tick: Positive
    minimum: Positive
    maximum: Positive
    step: Positive
    contract_value_per_unit: Positive
    fee_per_unit: Number = Field(ge=0)
    minimum_fee: Number = Field(ge=0)
    fixed_fee: Number = Field(ge=0)
    # Price points beyond planned exit, not a guaranteed maximum slippage.
    adverse_exit_price_allowance: Positive
    other_cost_allowance: Number = Field(ge=0)
    fee_evidence_hash: Hash
    assumptions_review_hash: Hash
    evidence_hash: Hash
    observed_at: Time
    valid_until: Time
    realized_loss_bounded: Literal[False]

    @model_validator(mode='after')
    def valid(self):
        if self.valid_until<=self.observed_at or self.maximum<self.minimum:
            raise ValueError('invalid demo risk policy')
        return self


def prepare(policy, entry, quote, economics, preconditions, now, *, quantity,
            margin_response, margin_observed_at):
    """Only trusted binding may supply correlated economics. No production Contract."""
    from trading_platform.execution.attended_preview import Quote, Preconditions
    p=DemoRiskPolicy.model_validate_json(policy.model_dump_json())
    entry=Entry.model_validate_json(entry.model_dump_json())
    q=Quote.model_validate_json(quote.model_dump_json())
    pre=Preconditions.model_validate_json(preconditions.model_dump_json())
    now=utc(now);quantity=decimal(quantity);at=utc(economics['observed_at'])
    if (p.account_id!=q.account_id or p.account_id!=pre.account_id or economics['account_id']!=p.account_id
            or p.instrument!=entry.instrument or q.instrument!=entry.instrument
            or pre.proposal_hash!=digest(entry) or pre.policy_hash!=digest(p)):
        raise ValueError('modeled preparation scope mismatch')
    if not p.observed_at<=now<p.valid_until or not now<pre.valid_until:
        raise ValueError('modeled policy expired')
    if any(not 0<=(now-t).total_seconds()<2 for t in (q.observed_at,at,pre.observed_at)):
        raise ValueError('stale modeled preparation')
    created=entry.expires_at-timedelta(seconds=60)
    if (not created<=now<=created+timedelta(seconds=10) or entry.side!='buy' or entry.order_type!='limit'
            or entry.profile!='protected' or entry.basis!='executable' or entry.exit_at is not None
            or entry.entry!=entry.worst_fill or entry.target is None or q.bid>q.ask or entry.entry>=q.ask):
        raise ValueError('unsupported modeled proposal')
    if any(v%p.tick for v in (entry.entry,entry.stop,entry.target)):
        raise ValueError('modeled price grid')
    if quantity!=p.minimum or not p.minimum<=quantity<=p.maximum:
        raise ValueError('modeled first test requires exact minimum quantity')
    wire=wire_volume(quantity)
    account=economics['account']
    if account['currency']!='USD':raise ValueError('modeled currency mismatch')
    equity=decimal(account['equity']);free=decimal(account['free_margin'])
    if equity<=0:raise ValueError('positive equity required')
    margin=expected_margin(margin_response,request=dict(ctidTraderAccountId=integer(p.account_id),symbolId=p.symbol_id,volume=[wire]),
        account=integer(p.account_id),symbol_id=p.symbol_id,volume=wire,side='BUY',observed_at=margin_observed_at,now=now)
    if margin<0:raise ValueError('negative expected margin')
    fees=max(quantity*p.fee_per_unit,p.minimum_fee)+p.fixed_fee
    allowance=quantity*p.contract_value_per_unit*p.adverse_exit_price_allowance+p.other_cost_allowance
    stop_loss=quantity*(entry.entry-entry.stop)*p.contract_value_per_unit
    loss=stop_loss+fees+allowance;budget=min(Decimal('5'),equity*Decimal('.001'))
    if loss<=0 or loss>budget or free-margin<equity*Decimal('.1'):
        raise ValueError('modeled loss or margin budget exceeded')
    blockers=[k.upper()+'_MISSING' for k in ('account_profile_review','price_grid_review','protection_review','costs_review','entry_expiry_review') if getattr(pre,k) is None]
    if not pre.connected or not pre.writer_fenced or not pre.reconciled_flat or pre.unresolved_commands:
        blockers.append('MODELED_PRECONDITIONS_UNSATISFIED')
    reconciliation=economics['reconciliation']
    if reconciliation.get('order') or reconciliation.get('position'):
        blockers.append('EXPOSURE_NOT_FLAT')
    expires=min(p.valid_until,pre.valid_until,at+timedelta(seconds=2),q.observed_at+timedelta(seconds=2),
                pre.observed_at+timedelta(seconds=2),margin_observed_at+timedelta(seconds=2))
    if expires<=now:blockers.append('PREVIEW_ALREADY_EXPIRED')
    body=dict(mode='attended_demo_modeled_preparation',risk_semantics='demo_modeled_risk',
        realized_loss_bounded=False,account_id=p.account_id,created_at=now,proposal_created_at=created,
        valid_until=expires,account_observed_at=at,entry=entry,quantity=quantity,bid=q.bid,ask=q.ask,
        spread=q.ask-q.bid,planned_loss=loss,modeled_loss=loss,loss_ceiling=budget,planned_stop_loss=stop_loss,
        reviewed_fees=fees,modeled_allowance=allowance,modeled_round_trip_costs=fees+allowance,
        margin=margin,margin_reserve_fraction=Decimal('.1'),risk_policy_hash=digest(p),
        assumptions_review_hash=p.assumptions_review_hash,
        evidence_hashes=dict(quote=digest(q),economics=digest(economics),preconditions=digest(pre),margin=digest(margin_response)),
        blockers=blockers,status='BLOCKED' if blockers else 'PREPARED_NOT_AUTHORIZED',orders_enabled=False)
    return dict(body,preview_hash=digest(body))
