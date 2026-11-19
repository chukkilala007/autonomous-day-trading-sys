"""Operator-declared demo configuration; never broker capability evidence."""
from typing import Literal
from pydantic import Field, model_validator
from trading_platform.contracts.values import Record, Name, Time, utc
from .broker_profile import AccountIdentity, Hash

Operation = Literal['BUY_LIMIT_ABSOLUTE_SLTP_GTD_60S', 'CANCEL_PENDING', 'CLOSE_POSITION']


class DemoConfiguration(Record):
    classification: Literal['operator_configured_demo_trial']
    identity: AccountIdentity
    instrument: Name
    symbol_id: int = Field(gt=0)
    operations: tuple[Operation, ...] = Field(min_length=1)
    # Human-readable explanations are part of the independently pinned bundle.
    assumptions: dict[str, str] = Field(min_length=1)
    review_hash: Hash
    observed_at: Time
    valid_until: Time

    @model_validator(mode='after')
    def scope(self):
        if self.identity.environment != 'demo' or self.valid_until <= self.observed_at:
            raise ValueError('current demo-only configuration required')
        if len(set(self.operations)) != len(self.operations):
            raise ValueError('duplicate trial operation')
        required = {'price_grid', 'contract_value', 'fees', 'financing_adjustments', 'protection', 'expiry', 'recovery'}
        if set(self.assumptions) != required or any(not v.strip() for v in self.assumptions.values()):
            raise ValueError('explicit assumptions for every configurable broker dependency required')
        return self

    def verify(self, profile, instrument, now):
        value = DemoConfiguration.model_validate_json(self.model_dump_json())
        mapping = next((m for m in profile.symbols if m.instrument == instrument), None)
        if (value.identity != profile.identity or value.instrument != instrument
                or mapping is None or value.symbol_id != mapping.symbol_id
                or not value.observed_at <= utc(now) < value.valid_until):
            raise ValueError('demo configuration scope or validity mismatch')
        return value
