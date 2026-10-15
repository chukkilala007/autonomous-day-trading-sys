"""Strict immutable boundary values and canonical evidence encoding."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def decimal(value):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('decimal requires exact text, integer or Decimal')
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('nonfinite decimal')
    return result


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone required')
    return value.astimezone(timezone.utc)


Number = Annotated[Decimal, BeforeValidator(decimal)]
Positive = Annotated[Number, Field(gt=0)]
Time = Annotated[datetime, BeforeValidator(utc)]
Name = Annotated[str, Field(min_length=1, pattern=r'^\S+$')]


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, validate_default=True)


def canonical(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode='python')
    def encode(obj):
        if isinstance(obj, Decimal):
            return format(obj.normalize(), 'f') if obj else '0'
        if isinstance(obj, datetime):
            return utc(obj).isoformat()
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode='python')
        raise TypeError(type(obj).__name__)
    return json.dumps(value, default=encode, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Money(Record):
    amount: Number
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]


class Identity(Record):
    account: Name
    environment: Name
    instrument: Name
    provider: Name
