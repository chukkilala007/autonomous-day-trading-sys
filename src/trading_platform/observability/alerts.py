"""Durable transition alerts; no external messages or free-form secret payloads."""
import json
from trading_platform.contracts.values import canonical,digest


class Alerts:
    def __init__(self,db): self.db=db

    def transition(self,key,active,code,at):
        if code not in ('DATA_STALE','BROKER_UNAVAILABLE','INSTANCE_HALTED','RISK_HALTED'): raise ValueError('unknown alert code')
        if type(active)!=bool: raise ValueError('active must be boolean')
        state_key='alert-state:'+digest(key)
        with self.db.transaction() as c:
            old=c.execute('SELECT body FROM checkpoints WHERE id=?',(state_key,)).fetchone()
            prior=json.loads(old['body']) if old else None
            if prior and prior['active']==active and prior['code']==code: return None
            if not prior and not active: return None
            sequence=(prior or {}).get('sequence',0)+1
            state={'active':active,'code':code,'sequence':sequence,'at':at,'kind':'OPEN' if active else 'RECOVERED'}
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(state_key,canonical(state)))
            c.execute('INSERT INTO checkpoints VALUES (?,?)',('alert:'+digest((key,sequence)),canonical(state)))
        return state
