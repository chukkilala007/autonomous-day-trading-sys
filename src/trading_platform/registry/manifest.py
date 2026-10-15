from typing import Literal
from trading_platform.contracts.values import Record, Name
from pydantic import Field


class Manifest(Record):
    contract_version: Literal[1] = 1
    package: Name
    digest: Name
    entrypoint: Name
    subscriptions: tuple[str,...]
    capabilities: tuple[str,...] = ('protected',)
    state_version: int = Field(default=1, ge=1)
    max_evaluation_seconds: int = Field(default=5, ge=1, le=60)
    history: tuple[tuple[str,int],...] = ()
    dependencies: tuple[tuple[str,str],...] = ()
