"""Core-side demo gateway adapter: RPC only, no credentials or simulated fills."""
import json
from datetime import datetime,timezone
from trading_platform.contracts.values import utc
from trading_platform.execution.state_machine import BrokerEvent
from trading_platform.runtime.transport import request


class DemoBroker:
    execution_mode='demo'
    def __init__(self,host,port,token,account_id,core_id,*,call=None,now=None):
        self.account_id=str(account_id);self.core_id=core_id
        self.now=now or (lambda:datetime.now(timezone.utc))
        self._request=call or (lambda body:request(host,port,token,'demo-core',body,timeout=15))
        binding=self._request({'op':'acquire','account_id':self.account_id,'core_id':core_id})
        if binding.get('mode')!='demo' or str(binding.get('account_id'))!=self.account_id or binding.get('authorized') is not True:
            raise ValueError('authorized bound demo gateway required')
        self.epoch=binding['epoch'];self.authorized=True

    def call(self,op,**fields):
        return self._request(dict(op=op,core_id=self.core_id,epoch=self.epoch,account_id=self.account_id,**fields))

    def observe(self):
        view=self.call('observe')
        if view.get('mode')!='demo' or str(view.get('account_id'))!=self.account_id: raise ValueError('foreign broker observation')
        if not 0<=(self.now()-utc(view['observed_at'])).total_seconds()<=2: raise ValueError('stale broker observation')
        return view

    def events(self):
        view=self.observe()
        self.blockers=view['blockers']
        return [BrokerEvent.model_validate_json(json.dumps(e)) for e in view['events']]

    def account(self):
        view=self.observe()
        if view['blockers']: raise ValueError('broker valuation/reconciliation blockers')
        return view['account']

    def tick(self,quote,now): return []

    def submit(self,command,quote,now):
        # Any failure after crossing the RPC boundary is conservatively uncertain.
        try: result=self.call('submit',command=command)
        except (ValueError,OSError,TimeoutError) as exc: raise TimeoutError('demo submit requires reconciliation') from exc
        return [BrokerEvent.model_validate_json(json.dumps(e)) for e in result['events']]

    def manage(self,command,now):
        try: result=self.call('manage',command=command)
        except (ValueError,OSError,TimeoutError) as exc: raise TimeoutError('demo management requires reconciliation') from exc
        return [BrokerEvent.model_validate_json(json.dumps(e)) for e in result['events']]

    def management_confirmed(self,command_id): return self.call('management_confirmed',command_id=command_id) is True
