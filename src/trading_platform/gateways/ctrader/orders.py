"""Demo-only order boundary. No production service enables it by default."""
import json
from decimal import Decimal
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import canonical,digest,utc
from trading_platform.execution.planner import check_entry
from .normalization import wire_volume


class Fence:
    def __init__(self,db,account): self.db=db;self.key='gateway-fence:'+str(account)

    def acquire(self,core_id):
        if not core_id: raise ValueError('core identity required')
        with self.db.transaction() as c:
            row=c.execute('SELECT body FROM checkpoints WHERE id=?',(self.key,)).fetchone()
            epoch=json.loads(row['body'])['epoch']+1 if row else 1
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(self.key,canonical({'core':core_id,'epoch':epoch})))
        return epoch

    def check(self,core_id,epoch):
        row=self.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(self.key,)).fetchone()
        if not row or json.loads(row['body'])!={'core':core_id,'epoch':epoch}: raise ValueError('stale core fence')


def limit_fields(account,symbol,entry,quantity):
    # Absolute protection and server expiry are the first explicit supported profile.
    if entry.order_type!='limit' or entry.target is None: raise ValueError('unsupported demo execution profile')
    return dict(ctidTraderAccountId=int(account),symbolId=int(symbol),orderType=2,tradeSide=1 if entry.side=='buy' else 2,
        volume=wire_volume(quantity),limitPrice=float(entry.entry),stopLoss=float(entry.stop),takeProfit=float(entry.target),
        timeInForce=1,expirationTimestamp=int(entry.expires_at.timestamp()*1000))


class DemoTransport:
    def __init__(self,db,session,*,authorized=False):
        self.db=db;self.session=session;self.authorized=authorized;self.fence=Fence(db,session.account_id)

    def prepare(self,command,core_id,epoch,report,quote,now,account_observed_at):
        self.fence.check(core_id,epoch)
        if not self.authorized: raise ValueError('explicit demo qualification authorization required')
        if not self.session.ready: raise ValueError('broker account unavailable')
        if not 0<=(now-account_observed_at).total_seconds()<=2: raise ValueError('stale account')
        decision=command['body']['decision'];entry=Entry.model_validate_json(json.dumps(decision['proposal']))
        if decision['environment']!='demo': raise ValueError('demo mandate required')
        blockers=report.blockers(now,self.session.account_id,entry.instrument)
        if blockers: raise ValueError('provider capability blockers: '+','.join(blockers))
        check_entry(entry,quote,now)
        values={e.field:e.value for e in report.evidence}
        tick=Decimal(values['tick_grid'])
        if not tick.is_finite() or tick<=0: raise ValueError('invalid tick grid')
        for price in (entry.entry,entry.stop,entry.target):
            if price is None or price%tick: raise ValueError('price outside verified grid')
        volume=Decimal(command['body']['size']['quantity'])
        grid=json.loads(values['volume_grid']);minimum=Decimal(grid['min']);maximum=Decimal(grid['max']);step=Decimal(grid['step'])
        if not minimum<=volume<=maximum or step<=0 or (volume-minimum)%step: raise ValueError('volume outside verified grid')
        if values['session_state']!='OPEN' or values['expiry']!='GOOD_TILL_DATE' or 'limit' not in json.loads(values['order_types']): raise ValueError('unsupported provider capability')
        fields=limit_fields(self.session.account_id,values['symbol_id'],entry,volume)
        fields['clientOrderId']=command['id'][:50]
        # Correlation is evidence only; the broker does not promise idempotency.
        return fields

    def send(self,command,core_id,epoch,report,quote,now,account_observed_at):
        from twisted.internet import defer
        fields=self.prepare(command,core_id,epoch,report,quote,now,account_observed_at)
        key='gateway-send:'+command['id'];request_hash=digest(fields)
        with self.db.transaction() as c:
            if c.execute('SELECT 1 FROM checkpoints WHERE id=?',(key,)).fetchone(): raise ValueError('already attempted; reconcile without resend')
            c.execute('INSERT INTO checkpoints VALUES (?,?)',(key,canonical({'status':'UNKNOWN','hash':request_hash,'fields':fields,'instance':command['instance'],'at':now})))
        # Persist uncertainty BEFORE invoking a transport that could accept then time out.
        from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOANewOrderReq
        return self.session.client.send(ProtoOANewOrderReq(**fields),responseTimeoutInSeconds=10)
