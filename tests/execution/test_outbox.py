import json
from decimal import Decimal as D
import pytest
from trading_platform.persistence.database import Database
from trading_platform.execution.outbox import Executor
from trading_platform.execution.state_machine import BrokerEvent
from trading_platform.contracts.config import Instance
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.events import Quote
from trading_platform.risk.sizing import Contract
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import utc
T=utc('2024-01-01T00:00:00Z')

def setup(db):
    i=Instance.model_validate_json(json.dumps(dict(instance_id='a',strategy='fixture@1',package_digest='x',mode='paper',universe=['X'],account=dict(alias='paper',environment='paper'),allocation='0.005')))
    p=Entry(instrument='X',side='buy',order_type='market',worst_fill='100.02',stop='99',target='103',expires_at='2024-01-01T00:01:00Z')
    d=Decision(instance='a',account='paper',environment='paper',package='fixture@1',config_hash=i.hash,event_id='e',snapshot_hash='s',at=T,outcome='ENTRY',proposal=p)
    q=Quote(instrument='X',bid='100',ask='100.01',source_time=T,received_at=T)
    c=Contract(instrument='X',account_currency='GBP',valuation_currency='GBP',quote_to_account='1',contract_value_per_unit='1',commission_per_unit='.01',slippage_per_unit='.01',minimum='1',maximum='100',step='1',tick='.01',margin_per_unit='1',verified_at=T,provenance='fixture')
    ex=Executor(db,i.account);ex.book.limits.observe(T,D(10000))
    id=ex.enqueue(d,i,q,c,T,D(10000),D(10000),D(10000),'X')
    return ex,id,q


def test_unknown_keeps_risk_and_no_retry(tmp_path):
    with Database(tmp_path/'db') as db:
        ex,id,q=setup(db)
        class Broker:
            def submit(self,*args): raise TimeoutError()
        ex.dispatch(id,Broker(),q,T)
        assert ex.command(id)['status']=='UNKNOWN'
        assert db.connection.execute('SELECT status FROM reservations').fetchone()[0]=='RESERVED'
        with pytest.raises(ValueError): ex.dispatch(id,Broker(),q,T)
        event=BrokerEvent(id='b',command=id,revision=1,kind='PART_FILLED',at=T,filled='2',average_price='100.01')
        assert ex.apply(event);assert not ex.apply(event)
        cancelled=event.model_copy(update={'id':'cancel','revision':2,'kind':'CANCELLED'})
        ex.apply(cancelled)
        assert db.connection.execute('SELECT status FROM reservations').fetchone()[0]=='OPEN'
        ex.apply(cancelled.model_copy(update={'id':'close','revision':3,'kind':'CLOSED','net':D('1')}))
        assert db.connection.execute('SELECT status FROM reservations').fetchone()[0]=='RELEASED'
        assert not db.connection.execute('SELECT 1 FROM positions').fetchone()


def test_reservation_and_command_rollback_together(tmp_path):
    with Database(tmp_path/'db') as db:
        db.connection.execute("CREATE TRIGGER fail_commands BEFORE INSERT ON commands BEGIN SELECT RAISE(ABORT,'injected'); END")
        with pytest.raises(Exception): setup(db)
        assert db.connection.execute('SELECT count(*) FROM reservations').fetchone()[0]==0
