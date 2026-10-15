"""Bounded time-splitting pagination; does not assume response sort direction."""
from twisted.internet import defer


@defer.inlineCallbacks
def complete_range(session,request,field,from_ms,to_ms,*,max_requests=128,**fields):
    if from_ms>to_ms: raise ValueError('invalid history range')
    pending=[(from_ms,to_ms)];rows=[];calls=0
    while pending:
        start,end=pending.pop();calls+=1
        if calls>max_requests: raise ValueError('history pagination budget exhausted')
        response=yield session.read(request,fromTimestamp=start,toTimestamp=end,**fields)
        if str(response.get('ctidTraderAccountId'))!=str(session.account_id): raise ValueError('foreign history response')
        if response.get('hasMore'):
            if end<=start: raise ValueError('history cannot be completely paginated at timestamp precision')
            middle=(start+end)//2;pending.extend(((start,middle),(middle+1,end)))
        else: rows.extend(response.get(field,[]))
    return rows
