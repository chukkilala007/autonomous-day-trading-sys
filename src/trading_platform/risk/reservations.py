from decimal import Decimal as D
from trading_platform.portfolio.arbiter import external_risk
from .limits import Limits


class RiskBook:
    def __init__(self,db,policy): self.db=db;self.policy=policy;self.limits=Limits(db,policy)

    def reserve_in(self,c,intent,instance,instrument,bucket,amount,balance,allocation,now,external=()):
        self.limits.check(c,now)
        if amount<=0 or allocation>self.policy.total_risk: raise ValueError('invalid allocation')
        old=c.execute('SELECT * FROM reservations WHERE id=?',(intent,)).fetchone()
        if old:
            if old['instance']!=instance or old['instrument']!=instrument or D(old['amount'])!=amount:
                raise ValueError('conflicting reservation')
            if old['status']=='RELEASED': raise ValueError('terminal intent cannot be revived')
            return False
        if c.execute("SELECT 1 FROM instances WHERE id=? AND (halt IS NOT NULL OR status='HALTED')",(instance,)).fetchone(): raise ValueError('INSTANCE_HALT')
        if c.execute("SELECT 1 FROM reservations WHERE instrument=? AND status!='RELEASED'",(instrument,)).fetchone(): raise ValueError('SYMBOL_OWNED')
        rows=c.execute("SELECT * FROM reservations WHERE status!='RELEASED'").fetchall()
        ext=external_risk(external)
        if any(e.get('instrument')==instrument for e in external): raise ValueError('EXTERNAL_SYMBOL_OWNED')
        if amount>balance*self.policy.per_trade: raise ValueError('TRADE_LIMIT')
        if amount+sum((D(r['amount']) for r in rows),D(0))+ext>balance*self.policy.total_risk: raise ValueError('ACCOUNT_LIMIT')
        if amount+sum((D(r['amount']) for r in rows if r['instance']==instance),D(0))>balance*allocation: raise ValueError('ALLOCATION_LIMIT')
        bucket_external=external_risk([e for e in external if e.get('bucket')==bucket])
        if amount+sum((D(r['amount']) for r in rows if r['bucket']==bucket),D(0))+bucket_external>balance*self.policy.concentration: raise ValueError('CONCENTRATION_LIMIT')
        c.execute('INSERT INTO reservations VALUES (?,?,?,?,?,?)',(intent,instance,instrument,bucket,str(amount),'RESERVED'))
        return True

    def reserve(self,*args,**kwargs):
        with self.db.transaction() as c: return self.reserve_in(c,*args,**kwargs)

    def release_in(self,c,intent,terminal):
        if terminal not in ('CLOSED','CANCELLED','EXPIRED','REJECTED'): raise ValueError('terminal evidence required')
        c.execute("UPDATE reservations SET status='RELEASED' WHERE id=?",(intent,))
