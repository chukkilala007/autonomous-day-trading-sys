"""Read-only strategy path: has no executor or broker mutation capability."""
import json
from trading_platform.runtime.journal import Journal
from trading_platform.runtime.scheduler import evaluate
from trading_platform.runtime.transport import request
from trading_platform.contracts.strategy import Evaluation


class ShadowRuntime:
    def __init__(self,db,registry,instances,workers=None):
        if any(i.mode!='shadow' for i in instances): raise ValueError('shadow instances required')
        if db.connection.execute('SELECT 1 FROM commands').fetchone(): raise ValueError('separate shadow database required')
        self.db=db;self.registry=registry;self.instances=instances;self.workers=workers or {};self.journal=Journal(db)
        for i in instances:
            plugin=registry.load(i);self.journal.register(i.instance_id,i.strategy,plugin.initialize(i))

    def process(self,event,snapshot,account):
        if not account['history_complete']: raise ValueError('incomplete account history')
        if any(account["account_id"]!=i.account.broker_account for i in self.instances): raise ValueError("account mandate mismatch")
        seq=self.journal.append(event);evidence=self.journal.snapshot(snapshot)
        for instance in self.instances:
            if account['account_id']!=instance.account.broker_account: raise ValueError('account mandate mismatch')
            row=self.db.connection.execute('SELECT * FROM instances WHERE id=?',(instance.instance_id,)).fetchone()
            if row['cursor']>=seq: continue
            _,manifest,plugin=self.registry.instances[instance.instance_id]
            portfolio=tuple(p for p in account['positions'] if p['owner']==instance.instance_id)
            if instance.instance_id in self.workers:
                host,port,token=self.workers[instance.instance_id]
                out=Evaluation.model_validate_json(json.dumps(request(host,port,token,instance.instance_id,dict(op='evaluate',instance=json.loads(instance.model_dump_json()),event=json.loads(event.model_dump_json()),snapshot=json.loads(snapshot.model_dump_json()),portfolio=portfolio,state=row['state']),timeout=manifest.max_evaluation_seconds)))
            else: out=evaluate(plugin,manifest,instance,event,snapshot,portfolio,row['state'])
            for decision in out.decisions:
                if (decision.instance,decision.account,decision.environment,decision.package,decision.config_hash,decision.snapshot_hash,decision.at)!=(instance.instance_id,instance.account.alias,instance.account.environment,instance.strategy,instance.hash,evidence,snapshot.cutoff): raise ValueError('shadow evidence mismatch')
            self.journal.commit(instance.instance_id,seq,out)
            with self.db.transaction() as c: c.execute("UPDATE instances SET status='READY' WHERE id=?",(instance.instance_id,))
        return {'mode':'shadow','event':event.event_id,'submission_enabled':False}
