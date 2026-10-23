"""Versioned broker/account scope. Configuration is never authentication or approval."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from trading_platform.contracts.values import Record, Name, Positive, Time, digest, utc

Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Label = Annotated[str, Field(min_length=1, pattern=r'^\S(?:.*\S)?$')]


class AccountIdentity(Record):
    broker: Label
    account_id: Name
    environment: Literal['demo', 'live']
    currency: Name
    account_type: Name


class SymbolMapping(Record):
    instrument: Name
    native_symbol: Name
    symbol_id: int = Field(gt=0)
    quote_currency: Name
    tick: Positive
    minimum: Positive
    maximum: Positive
    step: Positive
    contract_value_per_unit: Positive

    @model_validator(mode='after')
    def geometry(self):
        if self.maximum < self.minimum or (self.maximum-self.minimum) % self.step:
            raise ValueError('invalid volume geometry')
        return self


class CapabilityEvidence(Record):
    identity: AccountIdentity
    instrument: Name
    symbol_id: int = Field(gt=0)
    operation: Name
    state: Literal['supported', 'unsupported', 'unknown']
    classification: Literal['protocol', 'broker_verified', 'demo_observed', 'synthetic']
    source: Label
    source_hash: Hash
    observed_at: Time
    valid_until: Time

    @model_validator(mode='after')
    def interval(self):
        if self.valid_until <= self.observed_at:
            raise ValueError('invalid evidence interval')
        return self


class BrokerProfile(Record):
    version: Literal[1] = 1
    identity: AccountIdentity
    observed_at: Time
    valid_until: Time
    symbols: tuple[SymbolMapping, ...] = Field(min_length=1)
    evidence: tuple[CapabilityEvidence, ...] = ()

    @model_validator(mode='after')
    def scope(self):
        if self.valid_until <= self.observed_at:
            raise ValueError('invalid profile interval')
        for key in ('instrument', 'native_symbol', 'symbol_id'):
            if len({getattr(s, key) for s in self.symbols}) != len(self.symbols):
                raise ValueError('ambiguous symbol mapping')
        mappings = {(s.instrument, s.symbol_id) for s in self.symbols}
        keys = set()
        for e in self.evidence:
            if e.identity != self.identity or (e.instrument, e.symbol_id) not in mappings:
                raise ValueError('foreign evidence scope')
            key = (e.instrument, e.operation)
            if key in keys:
                raise ValueError('duplicate capability evidence')
            keys.add(key)
        return self

    @property
    def hash(self):
        return digest(self)

    def verify(self, *, authenticated_identity, approved_hash, now):
        """Caller must derive identity from its authenticated session, not config.

        Does not authenticate, establish session freshness or authorize orders.
        Runtime integration and authenticated identity extraction belong to F5.2s.
        Reparse at this boundary to reject unchecked model_copy/model_construct data.
        """
        profile = BrokerProfile.model_validate_json(self.model_dump_json())
        identity = AccountIdentity.model_validate_json(authenticated_identity.model_dump_json())
        if profile.hash != approved_hash:
            raise ValueError('profile pin mismatch')
        if identity != profile.identity:
            raise ValueError('authenticated identity mismatch')
        if not profile.observed_at <= utc(now) < profile.valid_until:
            raise ValueError('profile outside validity')
        return profile

    def capability(self, instrument, operation, *, authenticated_identity, approved_hash, now):
        profile = self.verify(authenticated_identity=authenticated_identity,
                              approved_hash=approved_hash, now=now)
        if instrument not in {s.instrument for s in profile.symbols}:
            raise ValueError('unmapped instrument')
        for e in profile.evidence:
            if e.instrument == instrument and e.operation == operation:
                if (e.classification in ('broker_verified', 'demo_observed')
                        and e.observed_at <= utc(now) < e.valid_until):
                    return e.state
        return 'unknown'
