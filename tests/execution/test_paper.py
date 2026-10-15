import runpy
from datetime import timedelta
from decimal import Decimal as D
from trading_platform.persistence.database import Database
from trading_platform.simulation.broker import PaperBroker
from trading_platform.execution.outbox import Executor


def test_timeout_reconciliation_and_restart(tmp_path):
    fixture=runpy.run_path('tests/execution/test_outbox.py');T=fixture['T']
    path=tmp_path/'broker.json'
    with Database(tmp_path/'db') as db:
        ex,id,q=fixture['setup'](db);broker=PaperBroker(path)
        class LostAck:
            def submit(self,*args): return broker.submit(*args,fault='timeout_after_accept')
        ex.dispatch(id,LostAck(),q,T)
        assert ex.command(id)['status']=='UNKNOWN'
        broker=PaperBroker(path)
        assert ex.reconcile(broker) and ex.command(id)['status']=='FILLED'
        assert len(broker.state['orders'])==1
        future=T+timedelta(seconds=1)
        q=q.model_copy(update={'bid':D('103'),'ask':D('103.01'),'source_time':future,'received_at':future})
        for e in broker.tick(q,future): ex.apply(e)
        assert ex.command(id)['status']=='CLOSED'
        assert ex.reconcile(PaperBroker(path))
        assert not db.connection.execute('SELECT 1 FROM positions').fetchone()


def test_partial_fill_and_tick_dedup(tmp_path):
    fixture=runpy.run_path('tests/execution/test_outbox.py');T=fixture['T']
    with Database(tmp_path/'db') as db:
        ex,id,q=fixture['setup'](db);broker=PaperBroker(max_fill='2')
        ex.dispatch(id,broker,q,T)
        assert ex.command(id)['status']=='PART_FILLED'
        future=T+timedelta(seconds=1)
        q=q.model_copy(update={'source_time':future,'received_at':future})
        events=broker.tick(q,future)
        assert broker.tick(q,future)==[]
        for e in events: ex.apply(e)
        assert ex.command(id)['body']['filled']=='4'


def test_stop_limit_nonfill_expiry_and_rejection(tmp_path):
    from trading_platform.contracts.orders import Entry
    fixture=runpy.run_path('tests/execution/test_outbox.py');T=fixture['T']
    with Database(tmp_path/'db') as db:
        ex,id,q=fixture['setup'](db);cmd=ex.command(id)
        p=Entry(instrument='X',side='buy',order_type='stop_limit',entry='101',limit='101',worst_fill='101',stop='99',target='105',expires_at=(T+timedelta(seconds=3)))
        cmd['body']['decision']['proposal']=__import__('json').loads(p.model_dump_json())
        broker=PaperBroker();assert broker.submit(cmd,q,T)[-1].kind=='ACCEPTED'
        later=T+timedelta(seconds=1)
        crossed=q.model_copy(update={'bid':D('101'),'ask':D('101.01'),'source_time':later,'received_at':later})
        assert broker.tick(crossed,later)==[]  # trigger crossed, limit cannot fill
        expiry=T+timedelta(seconds=3)
        assert broker.tick(crossed.model_copy(update={'source_time':expiry,'received_at':expiry}),expiry)[-1].kind=='EXPIRED'
        assert broker.state['orders'][id]['filled']=='0'
        rejected=PaperBroker().submit(cmd,q,T,fault='reject')
        assert rejected[-1].kind=='REJECTED'


def test_cancel_fill_race_preserves_exposure(tmp_path):
    import json
    from trading_platform.contracts.orders import Management
    from trading_platform.contracts.decisions import Decision
    fixture=runpy.run_path('tests/execution/test_outbox.py');T=fixture['T']
    with Database(tmp_path/'db') as db:
        ex,id,q=fixture['setup'](db);broker=PaperBroker(max_fill='2')
        ex.dispatch(id,broker,q,T)
        original=Decision.model_validate_json(json.dumps(ex.command(id)['body']['decision']))
        m=Management(target_id=id,owner='a',revision=1,action='cancel',expires_at=T+timedelta(seconds=20))
        d=original.model_copy(update={'outcome':'MANAGEMENT','proposal':m,'event_id':'cancel'})
        mid=ex.queue_management(d,T)
        ex.dispatch(mid,broker,q,T)
        assert ex.command(id)['status']=='CANCELLED'
        assert db.connection.execute('SELECT status FROM reservations').fetchone()[0]=='OPEN'
        future=T+timedelta(seconds=1)
        q=q.model_copy(update={'bid':D('98'),'ask':D('98.01'),'source_time':future,'received_at':future})
        for e in broker.tick(q,future): ex.apply(e)
        assert ex.command(id)['status']=='CLOSED'
        assert db.connection.execute('SELECT status FROM reservations').fetchone()[0]=='RELEASED'
