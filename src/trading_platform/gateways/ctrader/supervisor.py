"""Explicit demo-only protection recovery; never equates requests with closure."""
import json
from datetime import timedelta
from decimal import Decimal
from trading_platform.contracts.orders import Management
from trading_platform.contracts.values import canonical, digest, utc
from trading_platform.execution.recovery import DemoRecovery
from .management import send_owned


class ProtectionSupervisor:
    def __init__(self,gateway,ledger,*,repair_wait_seconds=5):
        if repair_wait_seconds<=0: raise ValueError('positive repair wait required')
        self.gateway=gateway;self.ledger=ledger;self.wait=repair_wait_seconds
        self.recovery=DemoRecovery(gateway.db,gateway.session.account_id)

    def step(self,position_id,core,epoch,now,account_observed_at):
        gateway=self.gateway;gateway.fence.check(core,epoch)
        if not gateway.authorized: raise ValueError('explicit demo authorization required')
        row=gateway.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('broker-position:'+str(position_id),)).fetchone()
        if not row: raise ValueError('position requires reconciliation')
        target=json.loads(row['body']);owner=target['owner']
        fresh=0<=(now-account_observed_at).total_seconds()<=2
        key='supervisor:'+str(position_id)
        row=gateway.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()
        state=json.loads(row['body']) if row else {}
        facts=dict(owned=owner is not None,open_quantity=0 if target['closed'] else Decimal(target['quantity']),protected=target['protected'],
                   connected=gateway.session.ready and fresh,repair_attempted='repair_at' in state,repair_confirmed=target['protected'])
        action=self.recovery.protection(position_id,**facts)
        if action not in ('REQUEST_PROTECTION_REPAIR','REQUEST_OWNED_CLOSE'): return action
        if action=='REQUEST_OWNED_CLOSE' and (now-utc(state['repair_at'])).total_seconds()<self.wait:
            return 'WAITING_FOR_PROTECTION_CONFIRMATION'
        operation='repair' if action=='REQUEST_PROTECTION_REPAIR' else 'close'
        if operation+'_at' in state: return 'WAITING_FOR_BROKER_CONFIRMATION'
        stop=target.get('expected',{}).get('stopLoss')
        if operation=='repair' and stop is None:
            # No verified intended stop exists: immediately choose owned closure.
            operation='close'
        if operation+'_at' in state: return 'WAITING_FOR_BROKER_CONFIRMATION'
        command_id=digest({'supervisor':str(position_id),'operation':operation})
        management=Management(target_id=str(position_id),owner=owner,revision=target['updated'],
                              action='protect' if operation=='repair' else 'close',
                              stop=Decimal(str(stop)) if operation=='repair' else None,expires_at=now+timedelta(seconds=2))
        # Persist before crossing the uncertain transport boundary. Restart never resends.
        state[operation+'_at']=now
        with gateway.db.transaction() as c:
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(key,canonical(state)))
        result=send_owned(gateway,self.ledger,command_id,owner,management,core,epoch,now)
        # A transport acknowledgement is not protection or closure confirmation.
        if hasattr(result,'addErrback'): result.addErrback(lambda failure:None)
        return 'REQUESTED_'+operation.upper()
