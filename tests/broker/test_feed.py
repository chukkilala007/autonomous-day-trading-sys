from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from trading_platform.persistence.database import Database
from trading_platform.market_data.service import Feed,history_window
from trading_platform.contracts.events import Bar,Quote
T=datetime(2026,1,1,tzinfo=timezone.utc)


def bar(end,price='1',available=None):
    return Bar(instrument='X',start=end-timedelta(minutes=1),end=end,available_at=available or end,basis='bid',open=price,high=price,low=price,close=price)


def test_gap_repair_revisions_and_stale_quotes(tmp_path):
    end=T+timedelta(minutes=3)
    with Database(tmp_path/'db') as db:
        feed=Feed(db);feed.ingest_bar(bar(T+timedelta(minutes=1)));feed.ingest_bar(bar(end))
        feed.ingest_quote(Quote(instrument='X',bid='1',ask='1.01',source_time=end,received_at=end))
        feed.repaired('X',end)
        assert not feed.snapshot(end,[('X','bid',1,3)]).coverage_complete
        feed.ingest_bar(bar(T+timedelta(minutes=2)))
        before=feed.snapshot(end,[('X','bid',1,3)])
        assert before.coverage_complete and len(before.bars)==3
        feed.disconnect('X');assert not feed.snapshot(end,[('X','bid',1,3)]).coverage_complete
        feed.repaired('X',end)
        assert not feed.snapshot(end+timedelta(seconds=3),[('X','bid',1,3)]).coverage_complete
        feed.ingest_bar(bar(end,'2',end+timedelta(seconds=1)))
        assert before.bars[-1].close==D(1)
        assert db.connection.execute('SELECT count(*) FROM revisions').fetchone()[0]==1
        assert not feed.snapshot(end,[('X','bid',1,3)]).coverage_complete
    with Database(tmp_path/'db') as db:
        assert Feed(db).get('coverage:X')['repaired']


def test_only_verified_closed_intervals_skip_gaps(tmp_path):
    end=T+timedelta(minutes=3)
    with Database(tmp_path/'db') as db:
        f=Feed(db);f.ingest_bar(bar(T+timedelta(minutes=1)));f.ingest_bar(bar(end));f.repaired('X',end)
        f.ingest_quote(Quote(instrument='X',bid='1',ask='1.01',source_time=end,received_at=end))
        assert f.snapshot(end,[('X','bid',1,2)],closed_intervals=[('X',T+timedelta(minutes=1),T+timedelta(minutes=2))]).coverage_complete
        assert history_window(end,end,1)==(end-timedelta(minutes=1),end)


def test_stream_history_incompleteness_and_foreign_quotes(tmp_path):
    import pytest
    pytest.importorskip('ctrader_open_api')
    from twisted.internet.defer import succeed
    from trading_platform.gateways.ctrader.stream import Stream
    class Session:
        generation=1;ready=True;account_id=12
        def read(self,name,**kw): return succeed({'hasMore':True,'ctidTraderAccountId':'12'} if 'Trendbars' in name else {})
    with Database(tmp_path/'db') as db:
        stream=Stream(Session(),Feed(db),{'X':1},[('X','bid',1,3)],lambda:T)
        errors=[];stream.repair().addErrback(lambda e:errors.append(e))
        assert errors and not stream.feed.get('coverage:X')['repaired']
        with pytest.raises(ValueError): stream.on_spot({'ctidTraderAccountId':'13','symbolId':'1'})


def test_incremental_overlap_and_reconnect_full_backfill(tmp_path):
    import pytest
    pytest.importorskip('ctrader_open_api')
    from twisted.internet.defer import succeed
    from trading_platform.gateways.ctrader.stream import Stream
    requests=[];clock=[T]
    class Session:
        generation=1;ready=True;account_id=12
        def read(self,name,**fields):
            requests.append((name,fields))
            rows=[]
            if 'fromTimestamp' in fields:
                rows=[dict(utcTimestampInMinutes=str(n),low='100000',deltaOpen='0',deltaHigh='0',deltaClose='0') for n in range(fields['fromTimestamp']//60000,fields['toTimestamp']//60000)]
            return succeed({'ctidTraderAccountId':'12','hasMore':False,'trendbar':rows})
    with Database(tmp_path/'db') as db:
        session=Session();stream=Stream(session,Feed(db),{'X':1},[('X','bid',1,100)],lambda:clock[0])
        errors=[];stream.repair().addErrback(errors.append)
        first=requests[-1][1]['fromTimestamp']
        clock[0]+=timedelta(seconds=10);stream.repair().addErrback(errors.append)
        assert not errors
        assert sum(name=='ProtoOASubscribeSpotsReq' for name,_ in requests)==1
        assert requests[-1][1]['fromTimestamp']==int((T-timedelta(minutes=2)).timestamp()*1000)
        assert requests[-1][1]['fromTimestamp']>first
        session.generation+=1;stream.repair().addErrback(errors.append)
        assert sum(name=='ProtoOASubscribeSpotsReq' for name,_ in requests)==2
        assert requests[-1][1]['fromTimestamp']==int((clock[0]-timedelta(minutes=102)).timestamp()*1000)
        assert not stream.feed.snapshot(clock[0],[('X','bid',1,100)]).coverage_complete


def test_partial_spots_preserve_oldest_side_age_and_reset_on_disconnect(tmp_path):
    import pytest
    pytest.importorskip('ctrader_open_api')
    from types import SimpleNamespace
    from trading_platform.gateways.ctrader.stream import Stream
    from trading_platform.contracts.values import utc
    clock=[T];base=int(T.timestamp()*1000)
    with Database(tmp_path/'db') as db:
        stream=Stream(SimpleNamespace(account_id=12),Feed(db),{'X':1},[('X','bid',1,1)],lambda:clock[0])
        def send(**fields):stream.on_spot(dict(ctidTraderAccountId='12',symbolId='1',**fields))
        send(timestamp=base,bid=100000,ask=100100)
        clock[0]+=timedelta(seconds=1)
        send(timestamp=base+1000,bid=100010)
        assert utc(stream.feed.get('quote:X')['source_time'])==T
        send(timestamp=base+1000,ask=100110)
        assert utc(stream.feed.get('quote:X')['source_time'])==clock[0]
        stream.disconnected()
        send(timestamp=base+2000,bid=100020)
        assert utc(stream.feed.get('quote:X')['source_time'])==clock[0]
        assert not stream.feed.get('coverage:X')['repaired']


def test_diagnostics_distinguish_history_gap_quote_age_and_repair(tmp_path):
    end=T+timedelta(minutes=3)
    with Database(tmp_path/'db') as db:
        feed=Feed(db);feed.ingest_bar(bar(end));feed.repaired('X',end)
        feed.ingest_quote(Quote(instrument='X',bid='1',ask='1.01',source_time=end,received_at=end))
        details=[]
        snapshot=feed.snapshot(end,[('X','bid',1,3)],diagnostics=details)
        assert not snapshot.coverage_complete
        history,quote=details
        assert history['contiguous_available']==1 and history['required']==3
        assert history['first_missing_end']==(end-timedelta(minutes=1)).isoformat()
        assert history['repaired'] and not history['complete'] and quote['complete']
        feed.ingest_bar(bar(end-timedelta(minutes=1)));feed.ingest_bar(bar(end-timedelta(minutes=2)))
        details=[]
        assert not feed.snapshot(end+timedelta(seconds=3),[('X','bid',1,3)],diagnostics=details).coverage_complete
        assert details[0]['complete'] and details[0]['first_missing_end'] is None
        assert details[1]['age_seconds']==3 and not details[1]['complete']
        feed.disconnect('X');details=[]
        assert not feed.snapshot(end,[('X','bid',1,3)],diagnostics=details).coverage_complete
        assert details[0]['contiguous_available']==3 and not details[0]['repaired']
        assert not details[0]['complete']


def test_diagnostics_preserve_verified_closure_and_missing_quote(tmp_path):
    end=T+timedelta(minutes=3)
    with Database(tmp_path/'db') as db:
        feed=Feed(db);feed.repaired('X',end)
        feed.ingest_bar(bar(end));feed.ingest_bar(bar(T+timedelta(minutes=1)))
        details=[]
        feed.snapshot(end,[('X','bid',1,2)],closed_intervals=[('X',T+timedelta(minutes=1),T+timedelta(minutes=2))],diagnostics=details)
        assert details[0]['complete'] and details[0]['contiguous_available']==2
        assert not details[1]['present'] and details[1]['age_seconds'] is None
