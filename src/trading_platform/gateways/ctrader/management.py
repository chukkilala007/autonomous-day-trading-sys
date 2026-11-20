"""Owned risk-reducing demo management, using authoritative ledger revisions."""
import json
from decimal import Decimal as D
from trading_platform.contracts.values import canonical,digest
from .normalization import wire_volume


def prepare(ledger,instance,management,now):
    target=(ledger.owned_order if management.action=='cancel' else ledger.owned)(management.target_id,instance)
    management.authorize(instance,target['owner'],target['updated'],now)
    if management.action=='cancel':
        return 'ProtoOACancelOrderReq',dict(orderId=int(management.target_id))
    if management.action=='close':
        return 'ProtoOAClosePositionReq',dict(positionId=int(management.target_id),volume=wire_volume(D(target['quantity'])))
    if management.action=='reduce':
        if management.quantity>D(target['quantity']): raise ValueError('reduction exceeds owned quantity')
        return 'ProtoOAClosePositionReq',dict(positionId=int(management.target_id),volume=wire_volume(management.quantity))
    if management.action=='protect':
        existing=target['record'].get('stopLoss');side=target['record']['tradeData'].get('tradeSide')
        if side not in ('BUY','SELL'): raise ValueError('unknown protection side')
        if existing is not None and ((side=='BUY' and management.stop<D(str(existing))) or (side=='SELL' and management.stop>D(str(existing)))): raise ValueError('stop widening')
        return 'ProtoOAAmendPositionSLTPReq',dict(positionId=int(management.target_id),stopLoss=float(management.stop))
    raise ValueError('unsupported management action')


def send_owned(gateway,ledger,command_id,instance,management,core,epoch,now):
    gateway.fence.check(core,epoch)
    if not gateway.authorized or not gateway.session.ready: raise ValueError('authorized connected demo session required')
    target=(ledger.owned_order if management.action=='cancel' else ledger.owned)(management.target_id,instance)
    name,fields=prepare(ledger,instance,management,now)
    fields['ctidTraderAccountId']=gateway.session.account_id
    key='gateway-management:'+command_id
    with gateway.db.transaction() as c:
        if c.execute('SELECT 1 FROM checkpoints WHERE id=?',(key,)).fetchone(): raise ValueError('management already attempted')
        c.execute('INSERT INTO checkpoints VALUES (?,?)',(key,canonical({'status':'UNKNOWN','request':name,'fields':fields,'owner':instance,'target_revision':target['updated'],'target_quantity':target.get('quantity','0')})))
    from ctrader_open_api.messages import OpenApiMessages_pb2 as messages
    return gateway.session.client.send(getattr(messages,name)(**fields),responseTimeoutInSeconds=10)


def reconcile_cleanup(db, account, now):
    """Resolve owned target outcomes, never infer request acknowledgement or retry."""
    with db.transaction() as c:
        for row in c.execute("SELECT id,body FROM checkpoints WHERE id LIKE 'gateway-management:%'").fetchall():
            value=json.loads(row['body']);fields=value['fields']
            if value['status']!='UNKNOWN' or str(fields.get('ctidTraderAccountId'))!=str(account): continue
            if value['request']!='ProtoOAClosePositionReq': continue
            pid=str(fields['positionId'])
            position=c.execute('SELECT body FROM checkpoints WHERE id=?',('broker-position:'+pid,)).fetchone()
            if not position: continue
            position=json.loads(position['body'])
            if not position['closed'] or D(position['quantity'])!=0 or position['owner']!=value['owner']: continue
            settlements=[json.loads(r['body']) for r in c.execute("SELECT body FROM checkpoints WHERE id LIKE 'provider-settlement:%'")]
            matches=[s for s in settlements if s['position_id']==pid and s['complete'] and s['costs_complete']]
            if len(matches)!=1: continue
            s=matches[0]
            if D(fields['volume'])/100!=D(value['target_quantity']) or D(s['closed'])!=D(value['target_quantity']): continue
            send=c.execute('SELECT body FROM checkpoints WHERE id=?',('gateway-send:'+s['command_id'],)).fetchone()
            if not send or json.loads(send['body'])['instance']!=value['owner']: continue
            value.update(status='TARGET_RESOLVED',outcome='OWNED_POSITION_CLOSED',request_acceptance_confirmed=False,
                         reconciled_at=now,settlement_hash=digest(s))
            c.execute('UPDATE checkpoints SET body=? WHERE id=?',(canonical(value),row['id']))
