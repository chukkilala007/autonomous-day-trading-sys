"""Durable monitoring of an already-attempted test. Never submits entries."""
import json
from decimal import Decimal
from twisted.internet import defer, task
from trading_platform.contracts.values import canonical, digest, utc
from .provider import Provider
from .valuation import Valuation, export


class Monitor:
    def __init__(self, adapter, provider, *, now, enabled=False):
        if not isinstance(provider, Provider) or provider.session is not adapter.gateway.session or provider.db is not adapter.gateway.db:
            raise ValueError('bound broker provider required')
        self.adapter=adapter;self.provider=provider;self.db=provider.db;self.now=now
        self.enabled=enabled;self.busy=False;self.loop=None
        self.key='attended-monitor:'+adapter.approval.account_id
        self.generation=None

    def _read(self,key):
        row=self.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()
        return json.loads(row['body']) if row else None

    def _save(self,state):
        with self.db.transaction() as c:
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(self.key,canonical(state)))
        return state

    @defer.inlineCallbacks
    def tick(self):
        if not self.enabled: raise ValueError('attended monitoring disabled')
        if self.busy: return dict(status='BUSY')
        self.busy=True
        state=self._read(self.key) or dict(approval_hash=self.adapter.approved_hash,status='AWAITING_ATTEMPT',last_at=None)
        try:
            if state['approval_hash']!=self.adapter.approved_hash: raise ValueError('monitor approval changed')
            now=self.now()
            if state['status']=='CLOCK_HALTED' or (state['last_at'] and now<utc(state['last_at'])):
                state['status']='CLOCK_HALTED';return self._save(state)
            state['last_at']=now
            a=self.adapter;attempt=self._read(a.key)
            if not attempt:
                state['status']='AWAITING_ATTEMPT';return self._save(state)
            if attempt['approval_hash']!=a.approved_hash: raise ValueError('foreign consumed approval')
            a._check();generation=a.gateway.session.generation;revision=a.binding.revision
            bundle=yield self.provider.reconcile(reconnect=generation!=self.generation)
            if not self.enabled:
                state['status']='STOPPED_UNCONFIRMED';return self._save(state)
            a._check()
            if a.gateway.session.generation!=generation or a.binding.revision!=revision:
                raise ValueError('broker changed during monitor reconciliation')
            now=self.now()
            if now<utc(state['last_at']):
                state['status']='CLOCK_HALTED';return self._save(state)
            value=Valuation.model_validate_json(bundle['valuation'])
            export(value,a.approval.account_id,now)
            if (str(bundle['account_id'])!=a.approval.account_id or bundle['history_complete'] is not True
                    or not value.history_complete): raise ValueError('incomplete monitor history')
            if any(str(e.get('ctidTraderAccountId'))!=a.approval.account_id for e in bundle['execution_events']):
                raise ValueError('foreign execution history')
            for event in bundle['execution_events']: a.ledger.apply(event)
            self.provider.checkpoint(bundle)
            self.generation=generation
            send=self._read('gateway-send:'+attempt['command_id'])
            if not send or not send.get('broker_order_id'):
                state['status']='SUBMISSION_UNRESOLVED';return self._save(state)
            order=self._read('broker-order:'+send['broker_order_id'])
            if not order or order['owner']!=a.approval.test_id: raise ValueError('unowned original order')
            pid=order['record'].get('positionId')
            position=self._read('broker-position:'+str(pid)) if pid is not None else None
            if position and position['owner']!=a.approval.test_id: raise ValueError('unowned original position')
            pending=Decimal(order['remaining']) if not order['terminal'] else Decimal(0)
            opened=Decimal(position['quantity']) if position and not position['closed'] else Decimal(0)
            filled=Decimal(order['record'].get('executedVolume','0'))/100
            if min(pending,opened,filled)<0 or pending+opened>1000 or filled>1000:
                state['status']='EXPOSURE_BOUND_BREACH';return self._save(state)
            elapsed=(now-utc(attempt['at'])).total_seconds()
            if elapsed<0: state['status']='CLOCK_HALTED';return self._save(state)
            if state.get('completed_once') and (pending or opened or value.external_exposure is not False):
                state['status']='POST_COMPLETION_EXPOSURE_HALT';return self._save(state)
            if state['status']=='POST_COMPLETION_EXPOSURE_HALT': return self._save(state)
            actions=[]
            if pending and (elapsed>=20 or filled>0): actions.append(('cancel',send['broker_order_id']))
            if opened and (not position['protected'] or elapsed>=120): actions.append(('close',str(pid)))
            for action,target in actions:
                if not self.enabled:
                    state['status']='STOPPED_UNCONFIRMED';return self._save(state)
                key=digest(dict(approval=a.approval,action=action,target=str(target)))
                if self._read('gateway-management:'+key) is None:
                    yield a.manage(action,str(target))
            state['last_at']=self.now();state['reconciliation_hash']=digest(bundle)
            if value.external_exposure is not False: state['status']='EXTERNAL_EXPOSURE_HALT'
            elif order['terminal'] and not pending and not opened:
                if filled==0:
                    # No fill cannot qualify fees, cancellation refund or cash settlement.
                    state['status']='TERMINAL_UNFILLED_COST_REVIEW_REQUIRED'
                elif any(s.command_id==attempt['command_id'] and s.position_id==str(pid) for s in value.settlements):
                    state['status']='COMPLETE';state['completed_once']=True
                else: state['status']='AWAITING_SETTLEMENT'
            elif elapsed>=120: state['status']='CLEANUP_UNCONFIRMED'
            elif elapsed>=60: state['status']='EXPIRY_UNCONFIRMED'
            else: state['status']='MONITORING'
            return self._save(state)
        except Exception:
            # Never persist exception text which may contain provider/private data.
            state['status']='RECONCILIATION_REQUIRED'
            return self._save(state)
        finally:
            self.busy=False

    def start(self,clock,interval=1):
        if not self.enabled or self.loop is not None or not 0<interval<=1:
            raise ValueError('enabled single bounded monitor loop required')
        self.loop=task.LoopingCall(self.tick);self.loop.clock=clock
        return self.loop.start(interval,now=False)

    def stop(self):
        if self.loop is not None and self.loop.running:self.loop.stop()
        self.enabled=False
        # Stop does not cancel exposure or mark any test complete.
