import json
from trading_platform.persistence.database import Database
from trading_platform.execution.recovery import DemoRecovery


def test_unknown_requires_unique_complete_matching_history(tmp_path):
    with Database(tmp_path/'db') as db:
        fields={'clientOrderId':'a','symbolId':1,'volume':200,'tradeSide':1,'limitPrice':99}
        with db.transaction() as c: c.execute('INSERT INTO checkpoints VALUES (?,?)',('gateway-send:a',json.dumps({'status':'UNKNOWN','fields':fields})))
        r=DemoRecovery(db,12)
        order={'orderId':'9','clientOrderId':'a','tradeData':{'symbolId':'1','volume':'200','tradeSide':'BUY'},'limitPrice':99}
        assert r.reconcile({'ctidTraderAccountId':'12','order':[order]},history_complete=False)['gateway-send:a']=='UNRESOLVED'
        assert r.reconcile({'ctidTraderAccountId':'12','order':[order,order]},history_complete=True)['gateway-send:a']=='UNRESOLVED'
        assert r.reconcile({'ctidTraderAccountId':'12','order':[order]},history_complete=True)['gateway-send:a']=='OBSERVED'
        assert db.connection.execute('SELECT 1 FROM halts').fetchone()  # explicit resume required
        assert r.protection('9',owned=True,open_quantity=2,protected=False,connected=False,repair_attempted=True,repair_confirmed=False)=='HALT_UNABLE_TO_PROTECT_OR_CLOSE'
        saved=json.loads(db.connection.execute("SELECT body FROM checkpoints WHERE id='recovery:9'").fetchone()[0])
        assert not saved['confirmed']
