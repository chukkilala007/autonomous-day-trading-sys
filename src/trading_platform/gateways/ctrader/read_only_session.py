"""Read-only wire boundary and request-name audit; never records credentials."""
from collections import Counter
from .client import Session,READ_REQUESTS

AUTH_REQUESTS=frozenset(('ProtoOAApplicationAuthReq','ProtoOARefreshTokenReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq'))


class ReadOnlySession(Session):
    def __init__(self,*args,**kwargs):
        self.requests=Counter();self.rejected_writes=0
        super().__init__(*args,**kwargs)

    def wire(self,name,**fields):
        if name not in READ_REQUESTS|AUTH_REQUESTS:
            self.rejected_writes+=1
            raise ValueError('read-only wire rejects operation')
        self.requests[name]+=1
        return super().wire(name,**fields)


def summarize(metrics,requests,rejected_writes,*,reconnect_required):
    """Distinguish transport recovery from fresh-price/analysis acceptance."""
    writes=sum(count for name,count in requests.items() if name not in READ_REQUESTS|AUTH_REQUESTS)
    recovered=(metrics['reconnect_requested'] and metrics['disconnects']>0 and len(set(metrics['reconciled_generations']))>=2)
    reconnect_status='PASS' if recovered else ('INCOMPLETE' if reconnect_required else 'NOT_REQUESTED')
    if writes or rejected_writes:status='FAILED_READONLY_BOUNDARY'
    elif reconnect_required and not recovered:status='BLOCKED_RECONNECT'
    elif not metrics['complete_snapshots'] or not metrics['reconciliations']:status='BLOCKED_FRESH_COVERAGE'
    else:status='PASS'
    return dict(requests=dict(requests),rejected_writes=rejected_writes,order_writes=writes,reconnect_status=reconnect_status,status=status)
