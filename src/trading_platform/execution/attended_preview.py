"""Read-only preparation boundary. No authorization, transport or order writes.

Typed inputs are evidence claims, not independently authenticated broker facts.
A future adapter must obtain them from reviewed providers and recheck at send.
"""
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from pydantic import Field
from trading_platform.contracts.values import Record, Name, Positive, Time, digest, utc
from trading_platform.contracts.orders import Entry
from trading_platform.gateways.ctrader.valuation import Valuation, Hash, export
from trading_platform.risk.sizing import size


class Quote(Record):
    account_id: Name
    instrument: Literal['EURUSD']
    observed_at: Time
    bid: Positive
    ask: Positive
    evidence_hash: Hash


class Preconditions(Record):
    account_id: Name
    is_live: Literal[False]
    observed_at: Time
    valid_until: Time
    proposal_hash: Hash
    # Missing reviews are blockers; a capture alone does not establish these.
    account_profile_review: Hash | None = None
    price_grid_review: Hash | None = None
    protection_review: Hash | None = None
    costs_review: Hash | None = None
    entry_expiry_review: Hash | None = None
    source_hash: Hash
    image_digest: Hash
    policy_hash: Hash
    reconciled_flat: bool
    unresolved_commands: int = Field(ge=0)
    writer_fenced: bool
    connected: bool


def prepare(entry, quote, valuation, preconditions, now, *, proposal_created_at=None):
    """Return a hash-bound, expiring preview; never permission to submit."""
    now = utc(now)
    entry = Entry.model_validate_json(entry.model_dump_json())
    quote = Quote.model_validate_json(quote.model_dump_json())
    valuation = Valuation.model_validate_json(valuation.model_dump_json())
    p = Preconditions.model_validate_json(preconditions.model_dump_json())
    if len({p.account_id, quote.account_id, valuation.account_id}) != 1:
        raise ValueError('foreign preparation account')
    if p.proposal_hash != digest(entry):
        raise ValueError('reviewed proposal changed')
    if (entry.instrument != 'EURUSD' or entry.side != 'buy' or entry.order_type != 'limit'
            or entry.target is None or entry.worst_fill != entry.entry
            or not entry.stop < entry.entry < entry.target):
        raise ValueError('protected EURUSD BUY LIMIT required')
    created = now if proposal_created_at is None else utc(proposal_created_at)
    if not 0 <= (now-created).total_seconds() <= 10:
        raise ValueError('proposal collection window expired')
    if entry.expires_at != created + timedelta(seconds=60):
        raise ValueError('fresh exact 60-second proposed expiry required')
    if not 0 <= (now-quote.observed_at).total_seconds() <= 2:
        raise ValueError('stale quote')
    if not 0 <= (now-p.observed_at).total_seconds() <= 2 or not now < p.valid_until:
        raise ValueError('stale preparation state')
    if quote.bid > quote.ask or entry.entry >= quote.ask:
        raise ValueError('crossed quote or nonpassive buy limit')
    export(valuation, p.account_id, now)
    if valuation.currency != 'USD':
        raise ValueError('USD account required')
    contract = valuation.contracts.get('EURUSD')
    if contract is None or contract.exact_costs is None:
        raise ValueError('proposal-specific complete costs and margin required')
    if contract.exact_costs.account_id != p.account_id:
        raise ValueError('foreign economics')
    rows = [r for r in contract.exact_costs.rows if r.quantity == 1000]
    if len(rows) != 1:
        raise ValueError('minimum test quantity economics missing')
    # Restrict sizing to exactly the authorized preparation quantity, not a maximum affordable size.
    fixed = contract.model_copy(update={'exact_costs': contract.exact_costs.model_copy(update={'rows': tuple(rows)})})
    budget = min(Decimal('5'), valuation.equity * Decimal('0.001'))
    result = size(entry, fixed, budget, now=now, free_margin=valuation.free_margin,
                  equity=valuation.equity, reserve_fraction=Decimal('0.1'))
    blockers = [field.upper() + '_MISSING' for field in
                ('account_profile_review', 'price_grid_review', 'protection_review', 'costs_review', 'entry_expiry_review')
                if getattr(p, field) is None]
    for passed, reason in [(p.connected, 'DISCONNECTED'), (p.writer_fenced, 'WRITER_NOT_FENCED'),
                           (p.reconciled_flat, 'EXPOSURE_NOT_FLAT'), (p.unresolved_commands == 0, 'UNRESOLVED_COMMANDS'),
                           (valuation.history_complete, 'INCOMPLETE_HISTORY'),
                           (valuation.external_exposure is False, 'EXTERNAL_EXPOSURE_OR_UNKNOWN')]:
        if not passed: blockers.append(reason)
    expires = min(quote.observed_at+timedelta(seconds=2), valuation.observed_at+timedelta(seconds=2),
                  p.observed_at+timedelta(seconds=2), p.valid_until,
                  contract.exact_costs.observed_at+timedelta(seconds=2), contract.verified_at+timedelta(seconds=30))
    if expires <= now:
        blockers.append('PREVIEW_ALREADY_EXPIRED')
    body = dict(mode='attended_preparation', account_id=p.account_id, created_at=now, proposal_created_at=created,
                valid_until=expires, account_observed_at=valuation.observed_at, entry=entry, quantity=result.quantity, bid=quote.bid, ask=quote.ask,
                spread=quote.ask-quote.bid, planned_loss=result.risk, loss_ceiling=budget,
                modeled_round_trip_costs=rows[0].costs, margin=result.margin,
                margin_reserve_fraction=Decimal('0.1'), blockers=blockers,
                evidence_hashes=dict(quote=digest(quote), valuation=digest(valuation), preconditions=digest(p)),
                status='BLOCKED' if blockers else 'PREPARED_NOT_AUTHORIZED', orders_enabled=False,
                submission_adapter_implemented=False)
    return dict(body, preview_hash=digest(body))
