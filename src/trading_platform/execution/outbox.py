import json
from decimal import Decimal as D
from trading_platform.contracts.values import canonical
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.orders import Entry,Management
from trading_platform.portfolio.ownership import Portfolio
from trading_platform.risk.reservations import RiskBook
from .planner import plan,check_entry


class Executor:
    def __init__(self,db,policy): self.db=db;self.book=RiskBook(db,policy)

    def enqueue(self,decision,instance,quote,contract,now,balance,equity,free_margin,bucket,external=()):
        sized=plan(decision,instance,quote,contract,now,balance,equity,free_margin)
        body={'type':'entry','decision':json.loads(decision.model_dump_json()),'size':json.loads(sized.model_dump_json()),'contract':json.loads(contract.model_dump_json()),'filled':'0','broker_revision':-1}
        with self.db.transaction() as c:
            created=self.book.reserve_in(c,decision.id,instance.instance_id,decision.proposal.instrument,bucket,sized.risk,balance,instance.allocation,now,external)
            if created: c.execute('INSERT INTO commands(id,instance,instrument,body,status) VALUES (?,?,?,?,?)',(decision.id,instance.instance_id,decision.proposal.instrument,canonical(body),'QUEUED'))
        return decision.id

    def command(self,id):
        row=self.db.connection.execute('SELECT * FROM commands WHERE id=?',(id,)).fetchone()
        if not row: raise ValueError('unknown command')
        return dict(row)|{'body':json.loads(row['body'])}

    def queue_management(self,decision,now):
        m=decision.proposal
        if decision.outcome!='MANAGEMENT': raise ValueError('management required')
        target=self.command(m.target_id)
        m.authorize(decision.instance,target['instance'],target['revision'],now)
        if m.action=='protect':
            pos=self.db.connection.execute('SELECT body FROM positions WHERE id=?',(m.target_id,)).fetchone()
            if not pos: raise ValueError('position missing')
            p=json.loads(pos['body'])
            if (p['side']=='buy' and m.stop<D(p['stop'])) or (p['side']=='sell' and m.stop>D(p['stop'])): raise ValueError('stop widening prohibited')
        body={'type':'management','decision':json.loads(decision.model_dump_json()),'target':m.target_id}
        with self.db.transaction() as c:
            c.execute('INSERT OR IGNORE INTO commands(id,instance,instrument,body,status) VALUES (?,?,?,?,?)',(decision.id,decision.instance,target['instrument'],canonical(body),'QUEUED'))
        return decision.id

    def dispatch(self,id,broker,quote,now):
        cmd=self.command(id)
        if cmd['status']!='QUEUED': raise ValueError('already attempted; reconcile before retry')
        body=cmd['body'];decision=Decision.model_validate_json(json.dumps(body['decision']))
        if body['type']=='entry':
            from trading_platform.runtime.controls import Controls
            if Controls(self.db).state()['paused']: raise ValueError('OPERATOR_PAUSED')
            if self.db.connection.execute("SELECT 1 FROM commands WHERE status IN ('UNKNOWN','SUBMITTING')").fetchone():
                raise ValueError('UNKNOWN_BROKER_OUTCOME')
            check_entry(decision.proposal,quote,now)
            from trading_platform.contracts.values import utc
            if not 0 <= (now-utc(body['contract']['verified_at'])).total_seconds() <= 30:
                raise ValueError('STALE_VALUATION')
            with self.db.transaction() as c: self.book.limits.check(c,now)
        else:
            target=self.command(body['target'])
            decision.proposal.authorize(cmd['instance'],target['instance'],target['revision'],now)
        with self.db.transaction() as c:
            if body["type"]=="entry" and Controls(self.db).state()["paused"]: raise ValueError("OPERATOR_PAUSED")
            if c.execute("UPDATE commands SET status='SUBMITTING' WHERE id=? AND status='QUEUED'",(id,)).rowcount != 1:
                raise ValueError('command already claimed')
            c.execute('INSERT INTO attempts(command,at,outcome) VALUES (?,?,?)',(id,now.isoformat(),'SENDING'))
        try:
            events=broker.submit(cmd,quote,now) if body['type']=='entry' else broker.manage(cmd,now)
        except (TimeoutError,OSError):
            with self.db.transaction() as c:
                c.execute("UPDATE commands SET status='UNKNOWN' WHERE id=?",(id,))
                c.execute("UPDATE attempts SET outcome='UNKNOWN' WHERE command=?",(id,))
            return
        for event in events: self.apply(event)
        with self.db.transaction() as c:
            c.execute("UPDATE attempts SET outcome='ACKNOWLEDGED' WHERE command=?",(id,))
            if body['type']=='management': c.execute("UPDATE commands SET status='CLOSED' WHERE id=?",(id,))

    def recover_attempts(self):
        with self.db.transaction() as c:
            c.execute("UPDATE commands SET status='UNKNOWN' WHERE status='SUBMITTING'")

    def reconcile(self,broker):
        self.recover_attempts()
        for event in broker.events(): self.apply(event)
        with self.db.transaction() as c:
            for row in c.execute("SELECT id,body FROM commands WHERE status='UNKNOWN'").fetchall():
                body=json.loads(row['body'])
                if body['type']=='management' and broker.management_confirmed(row['id']):
                    c.execute("UPDATE commands SET status='CLOSED' WHERE id=?",(row['id'],))
        return self.db.connection.execute("SELECT count(*) FROM commands WHERE status='UNKNOWN'").fetchone()[0]==0

    def apply(self,event):
        with self.db.transaction() as c:
            previous=c.execute('SELECT body FROM broker_events WHERE id=?',(event.id,)).fetchone()
            if previous:
                if previous['body']!=canonical(event): raise ValueError('conflicting broker event')
                return False
            row=c.execute('SELECT * FROM commands WHERE id=?',(event.command,)).fetchone()
            if not row: raise ValueError('unowned broker event')
            body=json.loads(row['body'])
            if body['type']!='entry': raise ValueError('event target must be entry order')
            c.execute('INSERT INTO broker_events VALUES (?,?,?)',(event.id,event.command,canonical(event)))
            if event.revision<=body['broker_revision']: return False
            total=D(body['size']['quantity'])
            if event.kind=='FILLED' and event.filled!=total: raise ValueError('incomplete full fill')
            if event.kind=='PART_FILLED' and not 0<event.filled<total: raise ValueError('invalid partial fill')
            if event.filled<D(body['filled']) or event.filled>D(body['size']['quantity']): raise ValueError('invalid cumulative fill')
            prior_status=row['status']
            body.update(filled=str(event.filled),broker_revision=event.revision)
            entry=Entry.model_validate_json(json.dumps(body['decision']['proposal']))
            if event.stop is not None: entry=entry.model_copy(update={'stop':event.stop});body['decision']['proposal']=json.loads(entry.model_dump_json())
            c.execute('UPDATE commands SET body=?,status=?,revision=? WHERE id=?',(canonical(body),event.kind,event.revision,event.command))
            if event.filled>0 and event.kind!='CLOSED':
                position=dict(id=event.command,instance=row['instance'],instrument=row['instrument'],side=entry.side,quantity=str(event.open_quantity if event.open_quantity is not None else event.filled),entry_price=str(event.average_price),stop=str(entry.stop),target=None if entry.target is None else str(entry.target),exit_at=None if entry.exit_at is None else entry.exit_at.isoformat(),revision=event.revision,protected=event.protected)
                c.execute('INSERT OR REPLACE INTO positions VALUES (?,?,?,?)',(event.command,row['instance'],row['instrument'],canonical(position)))
                c.execute("UPDATE reservations SET status='OPEN' WHERE id=?",(event.command,))
                if not event.protected or prior_status in ('CANCELLED','EXPIRED','REJECTED','CLOSED'):
                    c.execute('INSERT OR REPLACE INTO halts VALUES (?,?)',(event.command,'UNPROTECTED_OR_UNEXPECTED_FILL'))
            if event.kind=='CLOSED':
                c.execute('DELETE FROM positions WHERE id=?',(event.command,))
                self.book.release_in(c,event.command,event.kind)
                # Realized outcome and its dedup marker commit with position closure.
                self.book.limits.record_trade_in(c,event.command,event.net,event.at)
            elif event.kind in ('CANCELLED','EXPIRED','REJECTED') and event.filled==0:
                self.book.release_in(c,event.command,event.kind)
        return True
