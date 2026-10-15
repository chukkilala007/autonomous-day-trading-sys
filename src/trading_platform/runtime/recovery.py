"""Persistent lifecycle; restart is not authorization to clear a halt."""
from trading_platform.runtime.journal import Journal


class Recovery:
    def __init__(self,db): self.db=db

    def status(self,instance):
        row=self.db.connection.execute('SELECT status,halt FROM instances WHERE id=?',(instance,)).fetchone()
        if not row: raise ValueError('unknown instance')
        return dict(row)

    def halt(self,instance,reason):
        with self.db.transaction() as c:
            c.execute("UPDATE instances SET status='HALTED',halt=? WHERE id=?",(reason,instance))

    def ready(self,instance,*,coverage,reconciled,explicit_resume=False):
        current=self.status(instance)
        if current['halt'] and not explicit_resume: raise ValueError('latched halt')
        if not coverage or not reconciled: raise ValueError('warmup or reconciliation incomplete')
        with self.db.transaction() as c:
            c.execute("UPDATE instances SET status='READY',halt=NULL WHERE id=?",(instance,))

    def restart(self,instance):
        current=self.status(instance)
        if not current['halt']:
            with self.db.transaction() as c:
                c.execute("UPDATE instances SET status='WARMING' WHERE id=?",(instance,))
        return self.status(instance)

    def replace(self,instance,new_package,plugin=None,prior_version=None):
        with self.db.transaction() as c:
            row=c.execute('SELECT * FROM instances WHERE id=?',(instance,)).fetchone()
            if not row: raise ValueError('unknown instance')
            unresolved=c.execute("SELECT count(*) FROM commands WHERE instance=? AND status NOT IN ('CLOSED','CANCELLED','EXPIRED','REJECTED')",(instance,)).fetchone()[0]
            positions=c.execute('SELECT count(*) FROM positions WHERE instance=?',(instance,)).fetchone()[0]
            if unresolved or positions: raise ValueError('drain old ownership before replacement')
            if plugin is None: raise ValueError('explicit state migration required')
            state=plugin.migrate_state(prior_version,row['state'])
            c.execute("UPDATE instances SET package=?,state=?,status='WARMING' WHERE id=?",(new_package,state,instance))
