from datetime import datetime, timezone, timedelta
import pytest
from trading_platform.gateways.ctrader.closures import certify, intervals
from trading_platform.market_data.service import Feed
from trading_platform.persistence.database import Database
from trading_platform.contracts.events import Bar, Quote

START = datetime(2026, 10, 19, 21, tzinfo=timezone.utc)
END = START + timedelta(hours=1)
NOW = END + timedelta(minutes=2)


def probe():
    return dict(status='COLLECTED', mode='demo-readonly', orders_enabled=False, account_id='12',
                collected_at=NOW.isoformat(), symbols={'X': 41},
                metadata={'ctidTraderAccountId': '12', 'symbol': [dict(
                    symbolId='41', tradingMode='ENABLED', scheduleTimeZone='UTC',
                    schedule=[dict(startSecond=79200,endSecond=161985),
                              dict(startSecond=165600,endSecond=248385)])]},
                gap_audit=dict(account_id='12', symbol_id='41', start=START.isoformat(), end=END.isoformat(),
                               observed_at=NOW.isoformat(), status='NO_TICKS_REPORTED', bar_count=0,
                               tick_counts={'bid':0,'ask':0}, response_hashes={k:'a'*64 for k in ('bars','bid','ask')},
                               repaired=False, orders_enabled=False))


def config(raw=None):
    return dict(symbols={'X':41}, verified_closures=[certify(raw or probe(),'X',NOW)])


@pytest.mark.parametrize('fault', ['ticks','bar','open','partial','foreign','stale','hash','duplicate'])
def test_closure_requires_schedule_and_complete_bound_empty_history(fault):
    raw=probe()
    if fault=='ticks':raw['gap_audit']['tick_counts']['bid']=1
    if fault=='bar':raw['gap_audit']['bar_count']=1
    if fault=='open':raw['metadata']['symbol'][0]['schedule'][0]['endSecond']=165600
    if fault=='partial':raw['metadata']['symbol'][0]['schedule'][0]['endSecond']=162001
    if fault=='foreign':raw['gap_audit']['account_id']='13'
    if fault in ('stale','hash','duplicate'):
        c=config()
        if fault=='hash':c['verified_closures'][0]['symbol']='OTHER'
        if fault=='duplicate':c['verified_closures']*=2
        with pytest.raises(ValueError):intervals(c,'12',NOW+timedelta(days=1) if fault=='stale' else NOW)
    else:
        with pytest.raises(ValueError):config(raw)


def test_snapshot_skips_only_evidenced_gap_without_creating_bars(tmp_path):
    c=config(); clock=[NOW]
    with Database(tmp_path/'db') as db:
        feed=Feed(db,lambda at:intervals(c,'12',at))
        ends=[START-timedelta(minutes=1), START, END+timedelta(minutes=1), NOW]
        for end in ends:
            feed.ingest_bar(Bar(instrument='X',start=end-timedelta(minutes=1),end=end,
                                available_at=NOW,basis='bid',open='1',high='1',low='1',close='1'))
        feed.ingest_quote(Quote(instrument='X',bid='1',ask='1.1',source_time=NOW,received_at=NOW))
        feed.repaired('X',NOW)
        result=feed.snapshot(NOW,[('X','bid',1,4)])
        assert result.coverage_complete and len(result.bars)==4
        assert not feed.snapshot(NOW,[('X','bid',1,5)]).coverage_complete
        assert not feed.snapshot(NOW,[('X','bid',1,4)],closed_intervals=[]).coverage_complete
        with pytest.raises(ValueError):feed.snapshot(NOW+timedelta(days=1),[('X','bid',1,4)])
        assert db.connection.execute("SELECT count(*) FROM checkpoints WHERE id LIKE 'bar:%'").fetchone()[0]==4


def test_foreign_timezone_holiday_cannot_open_regular_weekly_closure():
    raw=probe()
    raw['metadata']['symbol'][0]['holiday']=[dict(scheduleTimeZone='Europe/Moscow',
        isRecurring=False,holidayDate='20703',startSecond=73499,endSecond=86399)]
    assert intervals(config(raw),'12',NOW)==[('X',START,END)]


def test_cold_repair_fetches_history_before_closure_and_keeps_real_gap_blocked(tmp_path):
    pytest.importorskip('ctrader_open_api')
    from types import SimpleNamespace
    from twisted.internet.defer import succeed
    from trading_platform.gateways.ctrader.stream import Stream
    requests=[]
    def read(name,**fields):
        requests.append((name,fields))
        rows=[]
        if 'fromTimestamp' in fields:
            rows=[dict(utcTimestampInMinutes=str(n),low='100000',deltaOpen='0',deltaHigh='0',deltaClose='0')
                  for n in range(fields['fromTimestamp']//60000,fields['toTimestamp']//60000)
                  if not int(START.timestamp())//60<=n<int(END.timestamp())//60]
        return succeed(dict(ctidTraderAccountId='12',trendbar=rows))
    c=config()
    with Database(tmp_path/'db') as db:
        feed=Feed(db,lambda at:intervals(c,'12',at))
        stream=Stream(SimpleNamespace(generation=1,ready=True,account_id=12,read=read),
                      feed,{'X':41},[('X','bid',1,4)],lambda:NOW)
        errors=[];stream.repair().addErrback(errors.append)
        assert not errors
        assert requests[-1][1]['fromTimestamp']==int((NOW-timedelta(minutes=66)).timestamp()*1000)
        feed.ingest_quote(Quote(instrument='X',bid='1',ask='1.1',source_time=NOW,received_at=NOW))
        assert feed.snapshot(NOW,stream.requirements).coverage_complete
        stream.disconnected()
        assert not feed.snapshot(NOW,stream.requirements).coverage_complete
