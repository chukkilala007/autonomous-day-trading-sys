from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.task import Clock
from trading_platform.persistence.database import Database
from trading_platform.market_data.service import Feed
from trading_platform.contracts.events import Bar
from trading_platform.gateways.ctrader.stream import Stream
from trading_platform.gateways.ctrader.spot_buffer import SpotBuffer

T=datetime(2026,10,20,12,tzinfo=timezone.utc)


@pytest.fixture
def setup(tmp_path):
    with Database(tmp_path/'db') as db:
        clock=Clock();offset=[timedelta()];now=lambda:T+timedelta(seconds=clock.seconds())+offset[0]
        feed=Feed(db);session=SimpleNamespace(account_id=12,generation=1,ready=True)
        stream=Stream(session,feed,{'X':1,'Y':2},[('X','bid',1,1)],now)
        buffer=SpotBuffer(stream,clock,clock.seconds)
        feed.ingest_bar(Bar(instrument='X',start=T-timedelta(minutes=1),end=T,available_at=T,
                            basis='bid',open='1',high='1',low='1',close='1'))
        feed.repaired('X',T)
        def send(ms=0,symbol=1,**sides):
            raw=dict(ctidTraderAccountId='12',symbolId=str(symbol),timestamp=int(T.timestamp()*1000)+ms,**sides)
            buffer.on_spot(raw)
        yield SimpleNamespace(db=db,clock=clock,offset=offset,now=now,feed=feed,session=session,
                              stream=stream,buffer=buffer,send=send,
                              complete=lambda:feed.snapshot(now(),stream.requirements).coverage_complete)


def test_hold_blocks_old_quote_then_releases_at_original_timestamp(setup):
    s=setup;s.send(bid=100000,ask=100100);assert s.complete()
    s.send(20,bid=100010,ask=100110)
    assert not s.complete() and s.feed.get('quote:X')['bid']=='1'
    s.clock.advance(.019);assert not s.complete()
    s.clock.advance(.001);assert s.complete()
    q=s.feed.get('quote:X')
    assert datetime.fromisoformat(q['source_time'].replace('Z','+00:00'))==T+timedelta(milliseconds=20)
    assert datetime.fromisoformat(q['received_at'].replace('Z','+00:00'))>=T+timedelta(milliseconds=20)
    assert not s.stream.spot_rejections
    assert s.buffer.report()['counts']['released']==1


def test_partial_updates_remain_ordered_and_pending_blocks_intermediate_release(setup):
    s=setup;s.send(10,bid=100000);s.send(20,ask=100100)
    s.clock.advance(.01);assert not s.complete()
    s.clock.advance(.01);assert s.complete()
    q=s.feed.get('quote:X')
    assert datetime.fromisoformat(q['source_time'].replace('Z','+00:00'))==T+timedelta(milliseconds=10)
    s.clock.advance(2);assert not s.complete()


@pytest.mark.parametrize('fault,reason',[
    ('skew','BUFFER_EXCESSIVE_SKEW'),('order','BUFFER_OUT_OF_ORDER'),
    ('overflow','BUFFER_OVERFLOW'),('invalid','BUFFER_INVALID_SPOT')])
def test_bad_input_clears_pending_without_late_revival(setup,fault,reason):
    s=setup;s.send(bid=100000,ask=100100);s.send(50,bid=100010,ask=100110)
    if fault=='skew':s.send(101,bid=100010)
    if fault=='order':s.send(40,bid=100010)
    if fault=='invalid':s.send(60)
    if fault=='overflow':
        for _ in range(64):s.send(50,bid=100010)
    assert not s.buffer.pending and not s.complete()
    assert s.stream.spot_rejections[reason]==1
    s.clock.advance(.2);assert not s.complete()
    assert not s.stream.quote_sides


@pytest.mark.parametrize('fault',['backward','late_callback'])
def test_monotonic_residence_limit_survives_wall_clock_changes(setup,fault):
    s=setup;s.send(50,bid=100000,ask=100100)
    if fault=='backward':s.offset[0]=timedelta(seconds=-5)
    s.clock.advance(.250)
    assert not s.buffer.pending and not s.complete()
    assert s.stream.spot_rejections['BUFFER_EXPIRED']==1


def test_forward_clock_jump_does_not_make_stale_quote_fresh(setup):
    s=setup;s.send(20,bid=100000,ask=100100);s.offset[0]=timedelta(seconds=3)
    s.clock.advance(.02)
    assert not s.complete() and not s.buffer.pending


@pytest.mark.parametrize('fault',['disconnect','generation','not_ready'])
def test_old_callbacks_cannot_publish_after_connection_change(setup,fault):
    s=setup;s.send(20,bid=100000,ask=100100)
    if fault=='disconnect':s.stream.disconnected()
    if fault=='generation':s.session.generation+=1
    if fault=='not_ready':s.session.ready=False
    s.clock.advance(.05)
    assert not s.buffer.pending and not s.complete()
    assert not s.stream.quote_sides


def test_symbol_isolation_and_invalid_quote_at_release(setup):
    s=setup;s.send(10,bid=100200,ask=100100);s.send(20,symbol=2,bid=200000,ask=200100)
    s.clock.advance(.01);assert not s.complete()
    assert s.stream.spot_rejections['CROSSED_QUOTE']==1
    s.clock.advance(.01)
    assert s.feed.get('quote-valid:Y')['valid']
    assert not s.buffer.pending


def test_future_boundary_allowed_but_never_released_early(setup):
    s=setup;s.send(100,bid=100000,ask=100100)
    s.clock.advance(.099);assert not s.complete()
    s.clock.advance(.001);assert s.complete()


def test_generation_change_on_arrival_and_foreign_identity(setup):
    s=setup;s.send(20,bid=100000);s.session.generation+=1;s.send(30,ask=100100)
    assert not s.buffer.pending
    assert s.stream.spot_rejections['BUFFER_GENERATION_CHANGE']==1
    with pytest.raises(ValueError,match='foreign'):
        s.buffer.on_spot(dict(ctidTraderAccountId='99',symbolId='1',timestamp=0,bid=1))
    with pytest.raises(ValueError,match='unknown'):
        s.send(0,symbol=99,bid=100000)


def test_restart_removes_persisted_pending_but_does_not_reuse_old_quote(setup):
    s=setup;s.send(bid=100000,ask=100100);s.send(20,bid=100010)
    s.stream.disconnected()
    other=Stream(s.session,s.feed,{'X':1},s.stream.requirements,s.now)
    SpotBuffer(other,s.clock,s.clock.seconds)
    assert not s.feed.get('quote-buffer-pending:X')['pending']
    assert not s.complete()


def test_already_dispatched_old_callback_cannot_drain_replacement_queue(setup):
    s=setup;s.send(20,bid=100000,ask=100100);old=s.buffer.pending['X']
    s.stream.disconnected()
    s.send(30,bid=100020,ask=100120);replacement=s.buffer.pending['X']
    s.buffer._flush('X',old)
    assert s.buffer.pending['X'] is replacement
    assert not s.feed.get('quote-valid:X')['valid']
    s.clock.advance(.03)
    assert s.feed.get('quote:X')['bid']=='1.0002'
    assert not s.complete()  # Releasing a quote never repairs disconnected history.
    s.feed.repaired('X',s.now());assert s.complete()


def test_disabling_buffer_after_restart_clears_hold_without_reviving_quote(setup):
    s=setup;s.send(bid=100000,ask=100100);s.send(20,bid=100010)
    other=Stream(s.session,s.feed,{'X':1},s.stream.requirements,s.now)
    other.disconnected()
    assert not s.feed.get('quote-buffer-pending:X')['pending']
    assert not s.feed.get('quote-valid:X')['valid']
