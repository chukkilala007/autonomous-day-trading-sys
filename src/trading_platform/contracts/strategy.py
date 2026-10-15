from typing import Protocol
import json
from pydantic import model_validator
from .values import Record
from .decisions import Decision
from .events import Event
from .snapshots import Snapshot


class Evaluation(Record):
    state: str
    decisions: tuple[Decision,...] = ()

    @model_validator(mode="after")
    def state_object(self):
        if not isinstance(json.loads(self.state),dict): raise ValueError("state must be an object")
        return self


class Strategy(Protocol):
    def initialize(self, instance) -> str: ...
    def evaluate(self, instance, event: Event, snapshot: Snapshot, portfolio: tuple, state: str) -> Evaluation: ...
    def validate_proposal(self, proposal, snapshot: Snapshot) -> None: ...
    def migrate_state(self, prior_version: str, state: str) -> str: ...
