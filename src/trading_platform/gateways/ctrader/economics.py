"""Read-only cTrader account economics from scaled protocol money and server P&L.

Initial supported profile: hedged accounts, SUM margin, no account bonuses.
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


def account_money(account,trader,reconcile,pnl,assets):
    for response in (trader,reconcile,pnl,assets):
        if str(response.get('ctidTraderAccountId'))!=str(account): raise ValueError('foreign economics response')
    raw=trader['trader']
    if str(raw.get('ctidTraderAccountId'))!=str(account): raise ValueError('foreign trader')
    if raw.get('accountType')!='HEDGED' or raw.get('totalMarginCalculationType')!='SUM':
        raise ValueError('unsupported account margin profile')
    if any(integer(raw.get(k,0))!=0 for k in ('managerBonus','ibBonus','nonWithdrawableBonus')):
        raise ValueError('bonus valuation requires separate qualification')
    currencies=rows_by_id(assets.get('asset',[]),'assetId')
    currency=currencies[str(raw['depositAssetId'])]['name']
    if len(currency)!=3 or not currency.isascii() or not currency.isalpha() or not currency.isupper(): raise ValueError('unsupported account currency')
    positions=rows_by_id(reconcile.get('position',[]),'positionId')
    profits=rows_by_id(pnl.get('positionUnrealizedPnL',[]),'positionId')
    rows_by_id(reconcile.get('order',[]),'orderId')
    if set(positions)!=set(profits): raise ValueError('incomplete position P&L')
    balance=money(raw,'balance')
    if balance is None: raise ValueError('balance scale required')
    used=Decimal(0);net=Decimal(0)
    for pid,position in positions.items():
        if position.get('positionStatus')!='POSITION_STATUS_OPEN': raise ValueError('unexpected reconciled position status')
        margin=money(position,'usedMargin')
        profit=money(dict(profits[pid],moneyDigits=pnl['moneyDigits']),'netUnrealizedPnL')
        if margin is None or margin<0 or profit is None: raise ValueError('incomplete position economics')
        used+=margin;net+=profit
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
        trader=yield self.session.read('ProtoOATraderReq')
        reconciliation=yield self.session.read('ProtoOAReconcileReq')
        pnl=yield self.session.read('ProtoOAGetPositionUnrealizedPnLReq')
        check_trader=yield self.session.read('ProtoOATraderReq')
        check_positions=yield self.session.read('ProtoOAReconcileReq')
        if (not self.session.ready or self.session.generation!=generation or
                not 0<=(self.now()-started).total_seconds()<=2): raise ValueError('stale account economics')
        if 'balanceVersion' not in trader['trader'] or digest(trader)!=digest(check_trader) or digest(reconciliation)!=digest(check_positions):
            raise ValueError('account changed during valuation')
        account=account_money(self.session.account_id,trader,reconciliation,pnl,self.assets)
        return dict(account_id=str(self.session.account_id),observed_at=started.isoformat(),account=account,
                    evidence_hash=digest([trader,reconciliation,pnl,self.assets]),reconciliation=reconciliation,
                    trader=trader['trader'],classification='demo_observed')
