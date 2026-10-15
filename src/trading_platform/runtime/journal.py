import json
from trading_platform.contracts.values import canonical, digest
from trading_platform.contracts.events import Event


class Journal:
    def __init__(self, db): self.db=db

    def register(self, instance, package, state='{}'):
        with self.db.transaction() as c:
            row=c.execute('SELECT package FROM instances WHERE id=?',(instance,)).fetchone()
            if row and row['package']!=package: raise ValueError('instance already bound to another package')
            c.execute('INSERT OR IGNORE INTO instances(id,package,state) VALUES (?,?,?)',(instance,package,state))

    def append(self,event):
        body=canonical(event)
        with self.db.transaction() as c:
            prior=c.execute('SELECT seq,body FROM events WHERE id=?',(event.event_id,)).fetchone()
            if prior:
                if prior['body']!=body: raise ValueError('conflicting event revision; use a new event ID')
                return prior['seq']
            return c.execute('INSERT INTO events(id,body) VALUES (?,?)',(event.event_id,body)).lastrowid

    def snapshot(self,snapshot):
        body=canonical(snapshot);h=digest(snapshot)
        with self.db.transaction() as c:
            c.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(h,body))
        return h

    def evidence(self,h):
        row=self.db.connection.execute('SELECT body FROM snapshots WHERE hash=?',(h,)).fetchone()
        if not row or digest(json.loads(row['body']))!=h: raise ValueError('evidence missing or corrupt')
        return json.loads(row['body'])

    def revise(self,old,new):
        self.evidence(old);self.evidence(new)
        with self.db.transaction() as c: c.execute('INSERT INTO revisions(old_hash,new_hash) VALUES (?,?)',(old,new))

    def commit(self,instance,seq,evaluation,fail=False):
        # Every instance consumes every journal sequence, even if subscription says NO_ACTION.
        with self.db.transaction() as c:
            row=c.execute('SELECT cursor FROM instances WHERE id=?',(instance,)).fetchone()
            if not row: raise ValueError('unknown instance')
            if seq<=row['cursor']: return False
            if seq!=row['cursor']+1: raise ValueError('cursor would skip an event')
            event_row=c.execute('SELECT body FROM events WHERE seq=?',(seq,)).fetchone()
            if not event_row: raise ValueError('event missing')
            event=Event.model_validate_json(event_row['body'])
            json.loads(evaluation.state)
            for d in evaluation.decisions:
                if d.instance!=instance or d.event_id!=event.event_id: raise ValueError('decision attribution mismatch')
                self.evidence(d.snapshot_hash)
                c.execute('INSERT INTO decisions VALUES (?,?,?,?)',(d.id,instance,seq,canonical(d)))
            c.execute('UPDATE instances SET cursor=?,state=? WHERE id=?',(seq,evaluation.state,instance))
            if fail: raise RuntimeError('injected precommit failure')
        return True
