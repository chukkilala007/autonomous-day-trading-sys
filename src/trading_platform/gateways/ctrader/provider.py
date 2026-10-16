"""Read-only provider reconciliation for the disabled demo lifecycle.

Audited contracts and cost policy are supplied by the account-specific profile.
A missing position is never turned into a closed position by absence alone.
"""
import json
from decimal import Decimal
from twisted.internet import defer
from trading_platform.contracts.values import canonical,digest,utc
from trading_platform.execution.recovery import matches
from .economics import EconomicsCollector,rows_by_id
from .history import complete_range
from .settlement import settle
from .valuation import Valuation,Settlement,export
from .normalization import integer


def latest_orders(rows):
    result={}
    for row in rows:
        key=str(row['orderId']);old=result.get(key)
        if old is None: result[key]=row;continue
        a=integer(row['utcLastUpdateTimestamp']);b=integer(old['utcLastUpdateTimestamp'])
        if a==b and row!=old: raise ValueError('conflicting order revision')
        if a>b: result[key]=row
    return result


class Provider:
    def __init__(self,session,db,contracts,cost_policy,now):
        self.session=session;self.db=db;self.contracts=contracts;self.cost_policy=cost_policy;self.now=now
        self.economics=EconomicsCollector(session,now)

    @defer.inlineCallbacks
    def reconcile(self,*,reconnect=False):
        generation=self.session.generation;at=self.now()
        sends={r['id'].split(':',1)[1]:json.loads(r['body']) for r in self.db.connection.execute("SELECT id,body FROM checkpoints WHERE id LIKE 'gateway-send:%'")}
        saved={r['id'].split(':',1)[1]:Settlement.model_validate_json(r['body']) for r in self.db.connection.execute("SELECT id,body FROM checkpoints WHERE id LIKE 'provider-settlement:%'")}
        pending={k:v for k,v in sends.items() if k not in saved}
        order_rows=[];deals=[]
        start=min((utc(v['at']) for v in pending.values()),default=at)
        if start>at: raise ValueError('future intent history')
        if pending:
            fields=dict(from_ms=int(start.timestamp()*1000),to_ms=int(at.timestamp()*1000))
            order_rows=yield complete_range(self.session,'ProtoOAOrderListReq','order',**fields)
            deals=yield complete_range(self.session,'ProtoOADealListReq','deal',maxRows=1000,**fields)
            rows_by_id(deals,'dealId')
        economics=yield self.economics.collect()
        current=economics['reconciliation']
        orders=latest_orders(order_rows+current.get('order',[]))
        positions=rows_by_id(current.get('position',[]),'positionId')
        owned_orders=set();owned_positions=set();events=[];new_settlements={}
        account=str(self.session.account_id)
        for command,send in pending.items():
            candidates=[o for o in orders.values() if matches(send['fields'],o)]
            if len(candidates)!=1: raise ValueError('unresolved original order; never resend')
            order=candidates[0];oid=str(order['orderId']);owned_orders.add(oid)
            event=dict(ctidTraderAccountId=account,order=order)
            filled=Decimal(integer(order.get('executedVolume',0)))/100
            if filled:
                pid=str(order['positionId']);owned_positions.add(pid)
                if pid in positions: event['position']=positions[pid]
                else:
                    if order.get('orderStatus') not in ('ORDER_STATUS_FILLED','ORDER_STATUS_CANCELLED','ORDER_STATUS_EXPIRED'):
                        raise ValueError('pending entry remainder prevents final settlement')
                    position_deals=[d for d in deals if str(d['positionId'])==pid]
                    if any(str(d['symbolId'])!=str(send['fields']['symbolId']) for d in position_deals):
                        raise ValueError('settlement symbol mismatch')
                    settlement=settle(account,{'id':command,'currency':economics['account']['currency']},pid,oid,filled,
                                      position_deals,start,at,self.now(),self.cost_policy())
                    # Closure is derived from complete execution quantities AND
                    # a current reconciled absence, never disappearance alone.
                    entry_deals=[d for d in position_deals if 'closePositionDetail' not in d]
                    price=sum((Decimal(str(d['executionPrice']))*Decimal(integer(d['filledVolume'])) for d in entry_deals),Decimal(0))/(filled*100)
                    event['position']=dict(positionId=pid,positionStatus='POSITION_STATUS_CLOSED',
                        tradeData=dict(order['tradeData'],volume='0'),price=str(price),
                        utcLastUpdateTimestamp=str(max(integer(d['executionTimestamp']) for d in position_deals)))
                    event['settlement_evidence_hash']=settlement.evidence_hash
                    new_settlements[command]=settlement
            events.append(event)
        # Previously settled positions/orders reappearing is inconsistent state.
        for command,settlement in saved.items():
            if settlement.position_id in positions: raise ValueError('settled position reappeared')
            if command not in sends: raise ValueError('orphan settlement')
        external=any(str(o['orderId']) not in owned_orders for o in current.get('order',[])) or any(pid not in owned_positions for pid in positions)
        if self.session.generation!=generation or not self.session.ready: raise ValueError('provider connection changed')
        data=dict(mode='demo',account_id=account,observed_at=economics['observed_at'],classification='demo_observed',
                  evidence_hash=digest(dict(economics=economics,orders=orders,deals=deals)),**economics['account'],
                  history_complete=True,external_exposure=external,contracts=self.contracts(),
                  settlements=list(saved.values())+list(new_settlements.values()))
        value=Valuation.model_validate_json(canonical(data));export(value,account,self.now())
        # Settlements must commit with the ledger's derived closure downstream.
        # Do not cache them here: a crash before ledger.apply would hide history.
        return dict(account_id=account,history_complete=True,valuation=value.model_dump_json(),execution_events=events)

    def checkpoint(self,bundle):
        """Cache only after the durable execution ledger confirms owned closure."""
        value=Valuation.model_validate_json(bundle['valuation'])
        if value.account_id!=str(self.session.account_id): raise ValueError('foreign settlement checkpoint')
        with self.db.transaction() as c:
            for settlement in value.settlements:
                position=c.execute('SELECT body FROM checkpoints WHERE id=?',('broker-position:'+settlement.position_id,)).fetchone()
                send=c.execute('SELECT body FROM checkpoints WHERE id=?',('gateway-send:'+settlement.command_id,)).fetchone()
                if not position or not send: raise ValueError('durable closure required before cache')
                position=json.loads(position['body']);send=json.loads(send['body'])
                if not position['closed'] or position['owner']!=send['instance']: raise ValueError('owned closure required')
                key='provider-settlement:'+settlement.command_id;body=canonical(settlement)
                old=c.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()
                if old and old['body']!=body: raise ValueError('settlement evidence changed')
                c.execute('INSERT OR IGNORE INTO checkpoints VALUES (?,?)',(key,body))
