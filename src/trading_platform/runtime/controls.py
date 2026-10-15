"""Audited idempotent controls. Only core pumps owned execution actions."""
import json
from datetime import timedelta
from trading_platform.contracts.values import canonical,digest
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.orders import Management


class Controls:
    def __init__(self,db): self.db=db

    def state(self):
        row=self.db.connection.execute("SELECT body FROM checkpoints WHERE id='operations:control'").fetchone()
        return json.loads(row['body']) if row else {'paused':False}

    def submit(self,id,action,at,*,role):
        if role!='operator': raise ValueError('operator role required')
        if not isinstance(id,str) or not id or len(id)>128 or any(c.isspace() for c in id): raise ValueError('control ID required')
        if action not in ('pause','resume','flatten'): raise ValueError('unsupported control')
        key='control:'+id
        with self.db.transaction() as c:
            previous=c.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()
            if previous:
                body=json.loads(previous['body'])
                if body['action']!=action: raise ValueError('control ID conflict')
                return body
            body={'id':id,'action':action,'requested_at':at,'status':'QUEUED','role':role}
            c.execute('INSERT INTO checkpoints VALUES (?,?)',(key,canonical(body)))
            if action in ('pause','flatten'):
                c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('operations:control',canonical({'paused':True,'by':id})))
        return json.loads(canonical(body))

    def update(self,key,body,status,reason=None):
        body=dict(body,status=status,reason=reason)
        with self.db.transaction() as c: c.execute('UPDATE checkpoints SET body=? WHERE id=?',(canonical(body),key))

    def pump(self,runtime,now,snapshot):
        pending=self.db.connection.execute("SELECT id,body FROM checkpoints WHERE id LIKE 'control:%' ORDER BY rowid").fetchall()
        for row in pending:
            body=json.loads(row['body']);key=row['id']
            if body['status'] not in ('QUEUED','WAITING'): continue
            if body['action']=='pause': self.update(key,body,'COMPLETE');continue
            if body['action']=='resume':
                try:
                    if any(json.loads(r['body'])['action']=='flatten' and json.loads(r['body'])['status'] in ('QUEUED','WAITING') for r in pending): raise ValueError('FLATTEN_PENDING')
                    if snapshot is None or not snapshot.coverage_complete or not 0<=(now-snapshot.cutoff).total_seconds()<=2: raise ValueError('FRESH_COVERAGE_REQUIRED')
                    if not runtime.executor.reconcile(runtime.broker): raise ValueError('UNKNOWN_BROKER_OUTCOME')
                    if any(i['halt'] or i['status']!='READY' for i in runtime.status()['instances']): raise ValueError('INSTANCE_RECOVERY_REQUIRED')
                    with self.db.transaction() as c:
                        runtime.executor.book.limits.check(c,now)
                        c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('operations:control',canonical({'paused':False,'by':body['id']})))
                    self.update(key,body,'COMPLETE')
                except (ValueError,OSError,TimeoutError): self.update(key,body,'REJECTED','RESUME_CHECKS_FAILED')
                continue
            # A flatten request stays pending until broker-confirmed exposure is zero.
            if snapshot is None or not 0<=(now-snapshot.cutoff).total_seconds()<=2:
                self.update(key,body,'WAITING','FRESH_QUOTES_REQUIRED');continue
            try:
                if not runtime.executor.reconcile(runtime.broker): raise ValueError('UNKNOWN_BROKER_OUTCOME')
                for command in self.db.connection.execute('SELECT id,body,status,revision,instance,instrument FROM commands').fetchall():
                    raw=json.loads(command['body'])
                    if raw['type']!='entry': continue
                    if command['instance'] not in {i.instance_id for i in runtime.instances}: continue
                    position=self.db.connection.execute('SELECT body FROM positions WHERE id=?',(command['id'],)).fetchone()
                    if command['status']=='QUEUED':
                        with self.db.transaction() as c:
                            c.execute("UPDATE commands SET status='CANCELLED' WHERE id=? AND status='QUEUED'",(command['id'],))
                            runtime.executor.book.release_in(c,command['id'],'CANCELLED')
                        continue
                    if command['status'] in ('UNKNOWN','SUBMITTING'): raise ValueError('UNKNOWN_BROKER_OUTCOME')
                    action='cancel' if command['status'] in ('ACCEPTED','PART_FILLED') else 'close' if position else None
                    if action is None: continue
                    quote=next(q for q in snapshot.quotes if q.instrument==command['instrument'])
                    if not 0<=(now-quote.source_time).total_seconds()<=2: raise ValueError('STALE_QUOTE')
                    original=Decision.model_validate_json(json.dumps(raw['decision']))
                    management=Management(target_id=command['id'],owner=command['instance'],revision=command['revision'],action=action,expires_at=now+timedelta(seconds=30))
                    decision=original.model_copy(update={'outcome':'MANAGEMENT','proposal':management,'event_id':'control:'+digest((body['id'],command['id'],command['revision'],action)),'at':now,'snapshot_hash':runtime.journal.snapshot(snapshot)})
                    mid=runtime.executor.queue_management(decision,now)
                    if runtime.executor.command(mid)['status']=='QUEUED': runtime.executor.dispatch(mid,runtime.broker,quote,now)
                unresolved=self.db.connection.execute("SELECT 1 FROM reservations WHERE status!='RELEASED'").fetchone()
                if not unresolved and not self.db.connection.execute('SELECT 1 FROM positions').fetchone():
                    with self.db.transaction() as c: c.execute('INSERT OR REPLACE INTO halts VALUES (?,?)',('operator-flatten','FLATTENED_AND_HALTED'))
                    self.update(key,body,'COMPLETE')
                else: self.update(key,body,'WAITING','AWAITING_BROKER_CONFIRMATION')
            except (ValueError,OSError,TimeoutError,StopIteration): self.update(key,body,'WAITING','RECONCILIATION_OR_QUOTES_REQUIRED')
