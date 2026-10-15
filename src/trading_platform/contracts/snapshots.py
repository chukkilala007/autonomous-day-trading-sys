from pydantic import model_validator
from .events import Bar, Quote, Event
from .values import Record, Time, digest


class Snapshot(Record):
    cutoff: Time
    bars: tuple[Bar, ...] = ()
    quotes: tuple[Quote, ...] = ()
    features: tuple[Event, ...] = ()
    coverage_complete: bool = True

    @model_validator(mode='after')
    def causal(self):
        if any(b.available_at > self.cutoff for b in self.bars):
            raise ValueError('unpublished bar')
        if any(q.received_at > self.cutoff for q in self.quotes):
            raise ValueError('unobserved quote')
        if any(f.available_at > self.cutoff for f in self.features):
            raise ValueError('unpublished feature')
        return self

    @property
    def hash(self):
        return digest(self)
