from datetime import datetime,timezone,timedelta
import pytest
from trading_platform.execution.reconciliation import account_view
T=datetime(2026,1,1,tzinfo=timezone.utc)


def responses():
    return ({'ctidTraderAccountId':'12','trader':{'ctidTraderAccountId':'12','balance':'10000'}},
        {'ctidTraderAccountId':'12','position':[{'positionId':'7'},{'positionId':'8'}],'order':[]},
        {'ctidTraderAccountId':'12','deal':[]})


def test_unknown_ownership_and_incomplete_history_never_disappear():
    t,r,d=responses();view=account_view(12,t,r,d,{('position','7'):'a'},history_complete=False)
    assert [p['owner'] for p in view['positions']]==['a',None]
    assert view['entry_blockers'] and not view['submission_enabled']
    with pytest.raises(ValueError): account_view(13,t,r,d,{},history_complete=True)


def test_collector_uses_only_read_messages(tmp_path):
    pytest.importorskip('ctrader_open_api')
    from twisted.internet.defer import succeed
    from trading_platform.gateways.ctrader.readonly import Collector
    from trading_platform.persistence.database import Database
    sent=[];t,r,d=responses()
    class Session:
        generation=1;ready=True;account_id=12
        def read(self,name,**fields):
            sent.append(name)
            return succeed({'ProtoOATraderReq':t,'ProtoOAReconcileReq':r,'ProtoOADealListReq':d}[name])
    with Database(tmp_path/'db') as db:
        results=[];Collector(Session(),db,lambda:T).collect(T-timedelta(days=1)).addCallback(results.append)
        assert results and results[0]['history_complete']
        assert sent==['ProtoOATraderReq','ProtoOAReconcileReq','ProtoOADealListReq']
        assert not db.connection.execute('SELECT 1 FROM commands').fetchone()
