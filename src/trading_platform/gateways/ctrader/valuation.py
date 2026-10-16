"""Provider-neutral audited economics boundary; never infers broker fee semantics.

A provider exporter supplies exact account-currency cash movements, including
opening costs. Validation is not proof that a provider's mapping is correct.
"""
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import Field, model_validator
from trading_platform.contracts.values import Record, Name, Number, Positive, Time, digest
from trading_platform.risk.sizing import Contract

Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Currency = Annotated[str, Field(pattern=r'^[A-Z]{3}$')]


class CashMovement(Record):
    id: Name
    position_id: Name
    currency: Currency
    amount: Number
    # Signed account-currency cash movement, not an unsigned broker fee.
    evidence_hash: Hash


class Settlement(Record):
    command_id: Name
    position_id: Name
    opened: Positive
    closed: Positive
    complete: Literal[True]
    costs_complete: Literal[True]
    history_from: Time
    opened_at: Time
    closed_at: Time
    history_to: Time
    movements: tuple[CashMovement, ...]
    evidence_hash: Hash

    @model_validator(mode='after')
    def complete_position(self):
        if self.opened != self.closed: raise ValueError('unsettled position quantity')
        if not self.history_from <= self.opened_at <= self.closed_at <= self.history_to:
            raise ValueError('settlement history does not cover lifecycle')
        if not self.movements: raise ValueError('explicit cash movements required, including zero result')
        if any(m.position_id != self.position_id for m in self.movements): raise ValueError('foreign cash movement')
        if len({m.id for m in self.movements}) != len(self.movements): raise ValueError('duplicate cash movement')
        return self


class Valuation(Record):
    mode: Literal['demo']
    account_id: Name
    observed_at: Time
    classification: Literal['broker_verified', 'demo_observed']
    evidence_hash: Hash
    currency: Currency
    balance: Positive
    equity: Positive
    free_margin: Number
    history_complete: bool
    external_exposure: bool | None
    contracts: dict[str, Contract]
    settlements: tuple[Settlement, ...] = ()

    @model_validator(mode='after')
    def consistent(self):
        for symbol, contract in self.contracts.items():
            if symbol != contract.instrument or contract.account_currency != self.currency:
                raise ValueError('contract identity/currency mismatch')
        if len({s.command_id for s in self.settlements}) != len(self.settlements): raise ValueError('duplicate command settlement')
        if len({s.position_id for s in self.settlements}) != len(self.settlements): raise ValueError('duplicate position settlement')
        movements = [m for s in self.settlements for m in s.movements]
        if len({m.id for m in movements}) != len(movements): raise ValueError('cash movement allocated twice')
        if any(m.currency != self.currency for m in movements): raise ValueError('unconverted settlement')
        if any(s.history_to > self.observed_at for s in self.settlements): raise ValueError('future settlement')
        return self


def export(value, account_id, now):
    """Validate one immutable observation and adapt it to DemoAPI's callback."""
    # Revalidate even model instances: nested dictionaries are mutable.
    value = Valuation.model_validate_json(value.model_dump_json() if isinstance(value, Valuation) else value)
    if value.account_id != str(account_id): raise ValueError('foreign valuation account')
    if not 0 <= (now-value.observed_at).total_seconds() <= 2: raise ValueError('stale valuation')
    if any(not 0 <= (now-c.verified_at).total_seconds() <= 30 for c in value.contracts.values()):
        raise ValueError('stale contract economics')
    settlements = {s.command_id: dict(position_id=s.position_id, complete=True,
        net=str(sum((m.amount for m in s.movements), Decimal(0))), evidence_hash=digest(s)) for s in value.settlements}
    return dict(mode='demo', account_id=value.account_id, observed_at=value.observed_at.isoformat(),
        classification=value.classification, evidence_hash=digest(value),
        account=dict(currency=value.currency, balance=str(value.balance), equity=str(value.equity), free_margin=str(value.free_margin)),
        history_complete=value.history_complete, external_exposure=value.external_exposure,
        contracts={k:c.model_dump(mode='json') for k,c in value.contracts.items()}, settlements=settlements)
