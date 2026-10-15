"""Read-only account collection over the authenticated SDK session."""
from twisted.internet import defer
from trading_platform.execution.reconciliation import account_view,persist_view
from .history import complete_range


class Collector:
    def __init__(self,session,db,now): self.session=session;self.db=db;self.now=now

    @defer.inlineCallbacks
    def collect(self,from_time,owned_ids=None):
        at=self.now();generation=self.session.generation
        trader=yield self.session.read('ProtoOATraderReq')
        reconciliation=yield self.session.read('ProtoOAReconcileReq')
        rows=yield complete_range(self.session,'ProtoOADealListReq','deal',int(from_time.timestamp()*1000),int(at.timestamp()*1000),maxRows=1000)
        unique={}
        for row in rows:
            id=str(row['dealId'])
            if id in unique and unique[id]!=row: raise ValueError('conflicting deal history')
            unique[id]=row
        deals={'ctidTraderAccountId':str(self.session.account_id),'deal':list(unique.values()),'hasMore':False}
        if self.session.generation!=generation or not self.session.ready: raise ValueError('stale account collection')
        view=account_view(self.session.account_id,trader,reconciliation,deals,owned_ids or {},history_complete=not deals.get('hasMore',False))
        view['history_from']=from_time.isoformat();view['history_to']=at.isoformat()
        persist_view(self.db,view,at)
        return view
