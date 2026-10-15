from typing import Literal
from pydantic import Field,model_validator
from trading_platform.contracts.values import Record,Name,Time,Number,Positive


class BrokerEvent(Record):
    id: Name
    command: Name
    revision: int = Field(ge=0)
    kind: Literal['ACCEPTED','PART_FILLED','FILLED','CANCELLED','EXPIRED','REJECTED','CLOSED','PROTECTED','REDUCED']
    at: Time
    filled: Number = Field(default='0',ge=0)
    average_price: Positive | None = None
    protected: bool = True
    net: Number | None = None
    stop: Positive | None = None
    open_quantity: Number | None = Field(default=None,ge=0)

    @model_validator(mode='after')
    def valid(self):
        if self.filled>0 and self.average_price is None: raise ValueError('filled price missing')
        if self.kind=='CLOSED' and self.net is None: raise ValueError('closed net missing')
        return self
