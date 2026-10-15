from typing import Annotated, Literal
from pydantic import Field, model_validator
from .values import Record, Name, Time, digest
from .orders import Entry, Management


class Decision(Record):
    schema_version: Literal[1] = 1
    instance: Name
    account: Name
    environment: Name
    package: Name
    config_hash: Name
    event_id: Name
    snapshot_hash: Name
    at: Time
    outcome: Literal['NO_ACTION','WATCH','ENTRY','MANAGEMENT','UNAVAILABLE']
    proposal: Annotated[Entry | Management, Field(discriminator='kind')] | None = None
    reasons: tuple[str,...] = ()
    diagnostics: str = '{}'

    @model_validator(mode='after')
    def consistency(self):
        expected={'ENTRY':Entry,'MANAGEMENT':Management}.get(self.outcome)
        if expected and not isinstance(self.proposal,expected): raise ValueError('missing actionable proposal')
        if not expected and self.proposal is not None: raise ValueError('unexpected proposal')
        if self.proposal:
            if self.proposal.expires_at <= self.at: raise ValueError('expired proposal')
            if isinstance(self.proposal,Management) and self.proposal.owner != self.instance: raise ValueError('unowned proposal')
        return self

    @property
    def id(self): return digest(self)
