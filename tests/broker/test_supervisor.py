import json
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.defer import fail
from trading_platform.persistence.database import Database
from trading_platform.gateways.ctrader.orders import DemoTransport
from trading_platform.gateways.ctrader.execution import ExecutionLedger
from trading_platform.gateways.ctrader.supervisor import ProtectionSupervisor


def test_repair_timeout_closes_only_owned_once_across_restart(tmp_path):
    requests=[]
    class Client:
        def send(self,message,**kwargs):
            requests.append(message.DESCRIPTOR.name)
            return fail(TimeoutError())
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    with Database(tmp_path/'db') as db:
        session=SimpleNamespace(account_id=12,ready=True,client=Client())
        gateway=DemoTransport(db,session,authorized=True);epoch=gateway.fence.acquire('core')
        ledger=ExecutionLedger(db,12);supervisor=ProtectionSupervisor(gateway,ledger)
        body={'owner':'a','updated':100,'closed':False,'quantity':'2','protected':False,'expected':{'stopLoss':99},'record':{'tradeData':{'tradeSide':'BUY'}}}
        with db.transaction() as c: c.execute('INSERT INTO checkpoints VALUES (?,?)',('broker-position:2',json.dumps(body)))
        assert supervisor.step(2,'core',epoch,now,now)=='REQUESTED_REPAIR'
        assert supervisor.step(2,'core',epoch,now+timedelta(seconds=1),now)=='WAITING_FOR_PROTECTION_CONFIRMATION'
        later=now+timedelta(seconds=6);session.ready=False
        assert supervisor.step(2,'core',epoch,later,later)=='HALT_UNABLE_TO_PROTECT_OR_CLOSE'
        session.ready=True
        assert supervisor.step(2,'core',epoch,later,later)=='REQUESTED_CLOSE'
        assert ProtectionSupervisor(gateway,ledger).step(2,'core',epoch,later,later)=='WAITING_FOR_BROKER_CONFIRMATION'
        assert requests==['ProtoOAAmendPositionSLTPReq','ProtoOAClosePositionReq']
        assert ledger.owned(2,'a')['quantity']=='2'  # No invented successful closure.
        body['owner']=None
        with db.transaction() as c: c.execute('INSERT INTO checkpoints VALUES (?,?)',('broker-position:3',json.dumps(body)))
        assert supervisor.step(3,'core',epoch,later,later)=='OBSERVE_EXTERNAL'
        assert len(requests)==2

        body.update(owner='a',expected={})
        with db.transaction() as c: c.execute('INSERT INTO checkpoints VALUES (?,?)',('broker-position:4',json.dumps(body)))
        assert supervisor.step(4,'core',epoch,later,later)=='REQUESTED_CLOSE'
        assert supervisor.step(4,'core',epoch,later,later)=='WAITING_FOR_BROKER_CONFIRMATION'
        assert requests.count('ProtoOAClosePositionReq')==2
