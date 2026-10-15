from typing import Literal
from pydantic import model_validator
from .values import Record, Name, Time, Positive, canonical


class Quote(Record):
    instrument: Name
    bid: Positive
    ask: Positive
    source_time: Time
    received_at: Time
    basis: Literal['bid_ask'] = 'bid_ask'

    @model_validator(mode='after')
    def valid(self):
        if self.ask < self.bid or self.received_at < self.source_time:
            raise ValueError('inverted quote or future source')
        return self


class Bar(Record):
    instrument: Name
    start: Time
    end: Time
    available_at: Time
    basis: Literal['bid', 'ask']
    open: Positive
    high: Positive
    low: Positive
    close: Positive

    @model_validator(mode='after')
    def valid(self):
        if self.end <= self.start or self.available_at < self.end:
            raise ValueError('bar not complete at availability')
        if not self.low <= min(self.open,self.close) <= max(self.open,self.close) <= self.high:
            raise ValueError('invalid OHLC')
        return self


class Event(Record):
    schema_version: Literal[1] = 1
    event_id: Name
    kind: Literal['bar', 'tick', 'timer', 'execution', 'health', 'feature']
    source_time: Time
    available_at: Time
    instrument: Name
    payload: str = '{}'

    @model_validator(mode='after')
    def valid(self):
        import json
        if self.available_at < self.source_time:
            raise ValueError('event available before source')
        canonical(json.loads(self.payload))
        return self
