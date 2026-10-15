import json,runpy,threading
from datetime import timedelta
import pytest
from trading_platform.persistence.database import Database
from trading_platform.runtime.shadow import ShadowRuntime
from trading_platform.simulation.replay import load_registry
from trading_platform.contracts.config import Instance
from trading_platform.runtime.transport import request
from trading_platform.market_data.service import Feed


def test_shadow_strategies_record_evidence_and_never_create_orders(tmp_path):
    instances,rows=runpy.run_path('tests/execution/test_runtime.py')['inputs']()
    shadow=[]
    for instance in instances:
        data=json.loads(instance.model_dump_json());data['mode']='shadow';data['account'].update(environment='demo',broker_account='12')
        shadow.append(Instance.model_validate_json(json.dumps(data)))
    with Database(tmp_path/'db') as db:
        runtime=ShadowRuntime(db,load_registry('config/registry.json'),shadow)
        for event,snapshot,_ in rows: runtime.process(event,snapshot,{'account_id':'12','history_complete':True,'positions':[]})
        assert db.connection.execute('SELECT count(*) FROM decisions').fetchone()[0]>0
        assert db.connection.execute('SELECT count(*) FROM commands').fetchone()[0]==0
        assert db.connection.execute('SELECT count(*) FROM reservations').fetchone()[0]==0


def test_paginated_history_splits_without_guessing_sort_direction():
    pytest.importorskip('ctrader_open_api')
    from twisted.internet.defer import succeed
    from trading_platform.gateways.ctrader.history import complete_range
    class Session:
        account_id=12
        def read(self,name,**fields):
            a,b=fields['fromTimestamp'],fields['toTimestamp']
            return succeed({'ctidTraderAccountId':'12','hasMore':b-a>1,'deal':[{'dealId':str(n)} for n in range(b,a-1,-1)]})
    results=[];complete_range(Session(),'ProtoOADealListReq','deal',0,7).addCallback(results.append)
    assert {r['dealId'] for r in results[0]}=={str(n) for n in range(8)}
    errors=[];complete_range(Session(),'ProtoOADealListReq','deal',0,7,max_requests=1).addErrback(lambda e:errors.append(e))
    assert errors


def test_snapshot_rpc_has_no_write_operation(tmp_path):
    pytest.importorskip('ctrader_open_api')
    from trading_platform.gateways.ctrader.snapshot_server import Server
    from datetime import datetime,timezone
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    class Session: ready=True
    with Database(tmp_path/'db') as db:
        feed=Feed(db);feed.put('shadow:account',{'observed_at':now,'history_complete':True,'account_id':'12'})
        server=Server(('127.0.0.1',0),'t'*40,Session(),feed,[],lambda:now)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            data=request('127.0.0.1',server.server_address[1],'t'*40,'shadow-core',{'op':'snapshot'})
            assert data['account']['account_id']=='12'
            with pytest.raises(ValueError): request('127.0.0.1',server.server_address[1],'t'*40,'shadow-core',{'op':'submit'})
        finally: server.shutdown();server.server_close();thread.join(5)
