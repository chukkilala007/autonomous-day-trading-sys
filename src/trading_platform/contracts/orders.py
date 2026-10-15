from typing import Literal
from pydantic import model_validator
from .values import Record, Name, Time, Positive


class Entry(Record):
    kind: Literal['entry'] = 'entry'
    instrument: Name
    side: Literal['buy','sell']
    order_type: Literal['market','limit','stop','stop_limit']
    entry: Positive | None = None
    limit: Positive | None = None
    worst_fill: Positive
    stop: Positive
    target: Positive | None = None
    exit_at: Time | None = None
    expires_at: Time
    profile: Name = 'protected'
    basis: Literal['executable','research'] = 'executable'

    @model_validator(mode='after')
    def geometry(self):
        if self.order_type != 'market' and self.entry is None:
            raise ValueError('pending entry requires trigger/limit price')
        if self.order_type == 'market' and self.entry is not None:
            raise ValueError('market entry has no pending trigger')
        if (self.order_type == 'stop_limit') != (self.limit is not None):
            raise ValueError('limit bound required only for stop-limit')
        if self.side == 'buy':
            valid = self.stop < self.worst_fill and (self.target is None or self.target > self.worst_fill)
        else:
            valid = self.stop > self.worst_fill and (self.target is None or self.target < self.worst_fill)
        if not valid: raise ValueError('invalid protective geometry')
        if self.target is None and self.exit_at is None: raise ValueError('exit rule required')
        return self


class Management(Record):
    kind: Literal['management'] = 'management'
    target_id: Name
    owner: Name
    revision: int
    action: Literal['cancel','close','reduce','protect']
    quantity: Positive | None = None
    stop: Positive | None = None
    expires_at: Time

    @model_validator(mode='after')
    def fields(self):
        if self.revision < 0: raise ValueError('negative revision')
        if (self.action == 'reduce') != (self.quantity is not None): raise ValueError('reduce quantity required')
        if (self.action == 'protect') != (self.stop is not None): raise ValueError('protect stop required')
        return self

    def authorize(self, instance, owner, revision, now):
        if self.owner != instance or owner != instance: raise ValueError('unowned target')
        if self.revision != revision: raise ValueError('stale revision')
        if now >= self.expires_at: raise ValueError('expired management')
