import json
from datetime import timedelta
from decimal import Decimal as D
from trading_platform.contracts.values import canonical,utc
from trading_platform.contracts.orders import Entry,Management
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.strategy import Evaluation


class Timer:
    def initialize(self,instance):
        if len(instance.universe)!=1 or json.loads(instance.parameters): raise ValueError('fixture requires one instrument and no parameters')
        return '{"entered":false}'

    def migrate_state(self,prior,state):
        if prior!='1': raise ValueError('unsupported migration')
        return state

    def validate_proposal(self,proposal,snapshot):
        if proposal.kind=='entry' and proposal.order_type!='market': raise ValueError('fixture uses market')

    def evaluate(self,instance,event,snapshot,portfolio,state):
        saved=json.loads(state);proposal=None;outcome='NO_ACTION';reasons=[]
        owned=[p for p in portfolio if p['instance']==instance.instance_id]
        if owned:
            position=owned[0]
            if snapshot.cutoff>=utc(position['exit_at']):
                proposal=Management(target_id=position['id'],owner=instance.instance_id,revision=position['revision'],action='close',expires_at=snapshot.cutoff+timedelta(seconds=30))
                outcome='MANAGEMENT'
        elif not saved['entered']:
            q=next((q for q in reversed(snapshot.quotes) if q.instrument==instance.universe[0]),None)
            if q is None or (snapshot.cutoff-q.source_time).total_seconds()>2:
                outcome='UNAVAILABLE';reasons=['FRESH_QUOTE_REQUIRED']
            else:
                proposal=Entry(instrument=q.instrument,side='buy',order_type='market',worst_fill=q.ask+D('.01'),stop=q.bid-D('1'),expires_at=snapshot.cutoff+timedelta(seconds=30),exit_at=snapshot.cutoff+timedelta(seconds=120))
                outcome='ENTRY';saved['entered']=True
        d=Decision(instance=instance.instance_id,account=instance.account.alias,environment=instance.account.environment,package=instance.strategy,config_hash=instance.hash,event_id=event.event_id,snapshot_hash=snapshot.hash,at=snapshot.cutoff,outcome=outcome,proposal=proposal,reasons=tuple(reasons))
        return Evaluation(state=canonical(saved),decisions=(d,))
