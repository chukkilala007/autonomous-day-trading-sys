"""Shared strategy/risk/outbox pipeline with a strictly bound demo adapter."""
from trading_platform.runtime.paper import PaperRuntime
from trading_platform.execution.demo_broker import DemoBroker


class DemoRuntime(PaperRuntime):
    mode='demo'
    def __init__(self,db,registry,instances,broker,workers=None,factors=None):
        if not isinstance(broker,DemoBroker) or not broker.authorized: raise ValueError('authenticated demo adapter required')
        if not instances or any(i.account.environment!='demo' or i.account.broker_account!=broker.account_id for i in instances):
            raise ValueError('demo account binding mismatch')
        super().__init__(db,registry,instances,broker,workers,factors)

    def contract_for(self,proposal,contracts):
        return self.broker.contract_for(proposal)

    def execution_time(self,snapshot):
        return self.broker.now()
