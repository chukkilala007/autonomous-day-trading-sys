"""Read-only cTrader account economics from scaled protocol money and server P&L.

Initial supported profile: hedged accounts, SUM or MAX margin, no account bonuses.
No quote-currency conversions or fee signs are invented here.
"""
from decimal import Decimal
from twisted.internet import defer
from trading_platform.contracts.values import digest
from .execution import money
from .normalization import integer


def rows_by_id(rows,key):
    result={}
    for row in rows:
        identity=str(row[key])
        if identity in result: raise ValueError('duplicate provider record')
        result[identity]=row
    return result


def funded_positions(reconcile):
    """Separate a strictly empty pending-order placeholder from funded exposure."""
    rows=rows_by_id(reconcile.get('position',[]),'positionId');opened={}
    for pid,p in rows.items():
        trade=p.get('tradeData',{})
        # Some cTrader brokers expose a reserved pending-order position as
        # OPEN rather than CREATED even though its volume and economics are
        # still exactly zero. Only the fully linked zero placeholder below is
        # excluded; missing/positive volume remains funded exposure.
        volume=integer(trade.get('volume',-1))
        if p.get('positionStatus')=='POSITION_STATUS_OPEN' and volume!=0:
            opened[pid]=p;continue
        linked=[o for o in reconcile.get('order',[]) if str(o.get('positionId'))==pid]
        if (p.get('positionStatus') not in ('POSITION_STATUS_CREATED','POSITION_STATUS_OPEN') or volume!=0
                or any(money(p,k)!=0 for k in ('usedMargin','commission','swap')) or len(linked)!=1):
            raise ValueError('unexpected reconciled position status')
        o=linked[0];ot=o.get('tradeData',{})
        if (o.get('orderStatus')!='ORDER_STATUS_ACCEPTED' or integer(o.get('executedVolume',-1))!=0
                or integer(ot.get('volume',0))<=0 or str(ot.get('symbolId'))!=str(trade.get('symbolId'))
                or trade.get('tradeSide') not in ('BUY','SELL') or ot.get('tradeSide')!=trade['tradeSide']):
            raise ValueError('unverified empty pending position')
    return opened


def account_money(account,trader,reconcile,pnl,assets):
    for response in (trader,reconcile,pnl,assets):
        if str(response.get('ctidTraderAccountId'))!=str(account): raise ValueError('foreign economics response')
    raw=trader['trader']
    if str(raw.get('ctidTraderAccountId'))!=str(account): raise ValueError('foreign trader')
    if raw.get('accountType')!='HEDGED' or raw.get('totalMarginCalculationType') not in ('SUM','MAX'):
        raise ValueError('unsupported account margin profile')
    if any(integer(raw.get(k,0))!=0 for k in ('managerBonus','ibBonus','nonWithdrawableBonus')):
        raise ValueError('bonus valuation requires separate qualification')
    currencies=rows_by_id(assets.get('asset',[]),'assetId')
    currency=currencies[str(raw['depositAssetId'])]['name']
    if len(currency)!=3 or not currency.isascii() or not currency.isalpha() or not currency.isupper(): raise ValueError('unsupported account currency')
    positions=funded_positions(reconcile)
    all_positions=rows_by_id(reconcile.get('position',[]),'positionId')
    profits=rows_by_id(pnl.get('positionUnrealizedPnL',[]),'positionId')
    orders=rows_by_id(reconcile.get('order',[]),'orderId')
    empty=set(all_positions)-set(positions)
    for pid in empty & set(profits):
        if any(money(dict(profits[pid],moneyDigits=pnl['moneyDigits']),k)!=0 for k in ('netUnrealizedPnL','grossUnrealizedPnL')):
            raise ValueError('nonzero empty-position P&L')
    # Observed cTrader shape: an accepted, wholly unfilled pending order can
    # have a zero P&L row keyed by its reserved position ID while Reconcile
    # omits the position row entirely. Treat only that exact linked zero row
    # as an empty placeholder; it is not funded exposure.
    pnl_only=set(profits)-set(all_positions)
    for pid in pnl_only:
        linked=[o for o in orders.values() if str(o.get('positionId'))==pid]
        row=dict(profits[pid],moneyDigits=pnl['moneyDigits'])
        if (len(linked)!=1 or linked[0].get('orderStatus')!='ORDER_STATUS_ACCEPTED'
                or integer(linked[0].get('executedVolume',-1))!=0
                or integer(linked[0].get('tradeData',{}).get('volume',0))<=0
                or linked[0].get('tradeData',{}).get('tradeSide') not in ('BUY','SELL')
                or any(money(row,k)!=0 for k in ('netUnrealizedPnL','grossUnrealizedPnL'))):
            raise ValueError('unverified P&L-only pending placeholder')
    if set(positions)!=set(profits)-empty-pnl_only: raise ValueError('incomplete position P&L')
    balance=money(raw,'balance')
    if balance is None: raise ValueError('balance scale required')
    used=Decimal(0);net=Decimal(0);sides={}
    for pid,position in positions.items():
        if position.get('positionStatus')!='POSITION_STATUS_OPEN': raise ValueError('unexpected reconciled position status')
        margin=money(position,'usedMargin')
        profit=money(dict(profits[pid],moneyDigits=pnl['moneyDigits']),'netUnrealizedPnL')
        if margin is None or margin<0 or profit is None: raise ValueError('incomplete position economics')
        if raw['totalMarginCalculationType']=='MAX':
            trade=position['tradeData'];symbol=integer(trade['symbolId']);side=trade['tradeSide']
            if symbol<=0 or side not in ('BUY','SELL'): raise ValueError('invalid margin grouping')
            group=sides.setdefault(symbol,{'BUY':Decimal(0),'SELL':Decimal(0)})
            group[side]+=margin
        else: used+=margin
        net+=profit
    if raw['totalMarginCalculationType']=='MAX':
        used=sum((max(group.values()) for group in sides.values()),Decimal(0))
    equity=balance+net
    return dict(currency=currency,balance=str(balance),equity=str(equity),free_margin=str(equity-used))


class EconomicsCollector:
    def __init__(self,session,now): self.session=session;self.now=now;self.assets=None;self.asset_generation=None

    @defer.inlineCallbacks
    def collect(self):
        generation=self.session.generation
        if not self.session.ready: raise ValueError('account not ready')
        if self.asset_generation!=generation:
            self.assets=yield self.session.read('ProtoOAAssetListReq');self.asset_generation=generation
        started=self.now()
        trader,reconciliation=yield defer.gatherResults([self.session.read('ProtoOATraderReq'),self.session.read('ProtoOAReconcileReq')],consumeErrors=True)
        pnl=yield self.session.read('ProtoOAGetPositionUnrealizedPnLReq')
        check_trader,check_positions=yield defer.gatherResults([self.session.read('ProtoOATraderReq'),self.session.read('ProtoOAReconcileReq')],consumeErrors=True)
        if (not self.session.ready or self.session.generation!=generation or
                not 0<=(self.now()-started).total_seconds()<=2): raise ValueError('stale account economics')
        if 'balanceVersion' not in trader['trader'] or digest(trader)!=digest(check_trader) or digest(reconciliation)!=digest(check_positions):
            raise ValueError('account changed during valuation')
        account=account_money(self.session.account_id,trader,reconciliation,pnl,self.assets)
        return dict(account_id=str(self.session.account_id),observed_at=started.isoformat(),account=account,
                    evidence_hash=digest([trader,reconciliation,pnl,self.assets]),reconciliation=reconciliation,
                    trader=trader['trader'],classification='demo_observed')
