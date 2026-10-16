"""Durable paper orchestration shared by in-process tests and Docker RPC."""
import json
from decimal import Decimal as D
from pathlib import Path
from trading_platform.contracts.values import canonical
from trading_platform.contracts.strategy import Evaluation
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.events import Quote
from trading_platform.runtime.journal import Journal
from trading_platform.runtime.recovery import Recovery
from trading_platform.runtime.scheduler import evaluate
from trading_platform.runtime.transport import request
from trading_platform.portfolio.ownership import Portfolio
from trading_platform.portfolio.arbiter import arbitrate
from trading_platform.execution.outbox import Executor
from trading_platform.risk.sizing import Contract
from trading_platform.runtime.controls import Controls


class PaperRuntime:
    mode="paper"
    def __init__(self,db,registry,instances,broker,workers=None,factors=None):
        self.db=db;self.registry=registry;self.instances=instances;self.broker=broker;self.workers=workers or {};self.factors=factors or {}
        self.controls=Controls(db);self.last_snapshot=None
        self.journal=Journal(db);self.recovery=Recovery(db);self.portfolio=Portfolio(db)
        if any(i.mode!=self.mode for i in instances): raise ValueError('runtime mode mismatch')
        if len({i.account.model_dump_json() for i in instances})!=1: raise ValueError('shared account policy required')
        if sum((i.allocation for i in instances),D(0))>instances[0].account.total_risk: raise ValueError('allocations exceed account ceiling')
        self.executor=Executor(db,instances[0].account)
        for i in instances:
            plugin=registry.load(i);self.journal.register(i.instance_id,i.strategy,plugin.initialize(i))
            self.recovery.restart(i.instance_id)
        self.reconciled=self.executor.reconcile(broker)

    def process(self,event,snapshot,contracts):
        self.last_snapshot=snapshot
        seq=self.journal.append(event);h=self.journal.snapshot(snapshot)
        # Broker state is authoritative, including fills that raced with a core restart.
        self.reconciled=self.executor.reconcile(self.broker)
        for q in snapshot.quotes:
            for execution in self.broker.tick(q,snapshot.cutoff): self.executor.apply(execution)
        account=self.broker.account()
        self.executor.book.limits.observe(snapshot.cutoff,D(account['equity']))
        decisions=[]
        for i in self.instances:
            row=self.db.connection.execute('SELECT * FROM instances WHERE id=?',(i.instance_id,)).fetchone()
            if row['cursor']>=seq: continue
            if row['halt']: continue
            try:
                self.recovery.ready(i.instance_id,coverage=snapshot.coverage_complete,reconciled=self.reconciled)
                bound,manifest,plugin=self.registry.instances[i.instance_id]
                positions=self.portfolio.positions(i.instance_id)
                if i.instance_id in self.workers:
                    host,port,token=self.workers[i.instance_id]
                    result=request(host,port,token,i.instance_id,dict(op='evaluate',instance=json.loads(i.model_dump_json()),event=json.loads(event.model_dump_json()),snapshot=json.loads(snapshot.model_dump_json()),portfolio=positions,state=row['state']),timeout=manifest.max_evaluation_seconds)
                    out=Evaluation.model_validate_json(json.dumps(result))
                else: out=evaluate(plugin,manifest,i,event,snapshot,positions,row['state'])
                for d in out.decisions:
                    if (d.instance,d.account,d.environment,d.package,d.config_hash,d.snapshot_hash,d.at)!=(i.instance_id,i.account.alias,i.account.environment,i.strategy,i.hash,h,snapshot.cutoff): raise ValueError('worker output evidence mismatch')
                    if d.proposal: plugin.validate_proposal(d.proposal,snapshot)
                self.journal.commit(i.instance_id,seq,out)
                decisions.extend(out.decisions)
            except (OSError,ValueError,TimeoutError) as exc:
                self.recovery.halt(i.instance_id,str(exc))
        # Reload committed decisions after a crash between evaluation and enqueue.
        stored=self.db.connection.execute('SELECT body FROM decisions WHERE event_seq=?',(seq,)).fetchall()
        decisions=[Decision.model_validate_json(r['body']) for r in stored]
        by_id={i.instance_id:i for i in self.instances}
        for d in arbitrate(decisions,{}):
            if d.outcome not in ('ENTRY','MANAGEMENT'): continue
            if self.db.connection.execute('SELECT 1 FROM commands WHERE id=?',(d.id,)).fetchone(): continue
            i=by_id[d.instance]
            try:
                if not self.reconciled: raise ValueError('UNKNOWN_BROKER_OUTCOME')
                if self.recovery.status(i.instance_id)['halt']: raise ValueError('INSTANCE_HALTED')
                if d.outcome=='ENTRY':
                    if self.controls.state()['paused']: raise ValueError('OPERATOR_PAUSED')
                    q=next(q for q in snapshot.quotes if q.instrument==d.proposal.instrument)
                    contract=contracts[d.proposal.instrument]
                    bucket=self.factors.get(d.proposal.instrument,{}).get(d.proposal.side,d.proposal.instrument)
                    id=self.executor.enqueue(d,i,q,contract,snapshot.cutoff,D(account['balance']),D(account['equity']),D(account['free_margin']),bucket)
                else: id=self.executor.queue_management(d,snapshot.cutoff)
            except (ValueError,KeyError,StopIteration) as exc:
                with self.db.transaction() as c: c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('rejection:'+d.id,canonical({'reason':str(exc),'decision':d.id})))
        for row in self.db.connection.execute("SELECT id,instrument FROM commands WHERE status='QUEUED'").fetchall():
            try:
                q=next(q for q in snapshot.quotes if q.instrument==row['instrument'])
                self.executor.dispatch(row['id'],self.broker,q,snapshot.cutoff)
            except (ValueError,StopIteration) as exc:
                # Only unattempted commands may be locally rejected and release risk.
                with self.db.transaction() as c:
                    if c.execute("UPDATE commands SET status='REJECTED' WHERE id=? AND status='QUEUED'",(row['id'],)).rowcount:
                        self.executor.book.release_in(c,row['id'],'REJECTED')
                    c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('rejection:'+row['id'],canonical({'reason':str(exc)})))
        return self.status()

    def status(self):
        c=self.db.connection
        return dict(instances=[dict(r) for r in c.execute('SELECT id,cursor,status,halt FROM instances')],orders=[dict(r) for r in c.execute('SELECT id,instance,status,revision FROM commands')],positions=[json.loads(r['body']) for r in c.execute('SELECT body FROM positions')],active_risk=[dict(r) for r in c.execute("SELECT * FROM reservations WHERE status!='RELEASED'")],rejections=[json.loads(r['body']) for r in c.execute("SELECT body FROM checkpoints WHERE id LIKE 'rejection:%'")])
