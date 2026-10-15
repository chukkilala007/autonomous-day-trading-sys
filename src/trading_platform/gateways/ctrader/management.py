"""Owned risk-reducing demo management, using authoritative ledger revisions."""
import json
from decimal import Decimal as D
from trading_platform.contracts.values import canonical,digest
from .normalization import wire_volume


def prepare(ledger,instance,management,now):
    target=ledger.owned(management.target_id,instance)
    management.authorize(instance,target['owner'],target['updated'],now)
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
    raise ValueError('position action unsupported; pending order cancellation requires order binding')


def send_owned(gateway,ledger,command_id,instance,management,core,epoch,now):
    gateway.fence.check(core,epoch)
    if not gateway.authorized or not gateway.session.ready: raise ValueError('authorized connected demo session required')
    name,fields=prepare(ledger,instance,management,now)
    fields['ctidTraderAccountId']=gateway.session.account_id
    key='gateway-management:'+command_id
    with gateway.db.transaction() as c:
        if c.execute('SELECT 1 FROM checkpoints WHERE id=?',(key,)).fetchone(): raise ValueError('management already attempted')
        c.execute('INSERT INTO checkpoints VALUES (?,?)',(key,canonical({'status':'UNKNOWN','request':name,'fields':fields,'owner':instance})))
    from ctrader_open_api.messages import OpenApiMessages_pb2 as messages
    return gateway.session.client.send(getattr(messages,name)(**fields),responseTimeoutInSeconds=10)
