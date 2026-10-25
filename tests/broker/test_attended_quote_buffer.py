from datetime import timedelta
from types import SimpleNamespace
import pytest
from twisted.internet import task
from trading_platform.gateways.ctrader.attended_binding import Binding
from trading_platform.gateways.ctrader.spot_buffer import configured_buffer
from trading_platform.gateways.ctrader import attended_binding as module
from test_attended_binding import rig,T,result
from test_preview_launcher import setup
from test_attended_launcher import config, modeled, adapter, connected
from trading_platform.gateways.ctrader import preview_launcher,attended_launcher


@pytest.mark.parametrize('value',[-1,1,101,True,'100'])
def test_bounds_cannot_be_widened(rig,value):
    with pytest.raises(ValueError):configured_buffer(rig.stream,task.Clock(),lambda:0,value)


def test_binding_routes_holds_and_releases_causally(rig,monkeypatch):
    x=rig;clock=task.Clock();now=[T]
    x.stream.now=lambda:now[0]
    buffer=configured_buffer(x.stream,clock,clock.seconds,100)
    binding=Binding(x.session,x.stream,x.db,x.bundle,approved_bundle_hash=x.binding.pin,
                    core_id='core',epoch=x.epoch,now=lambda:now[0],spot_buffer=buffer)
    monkeypatch.setattr(module.Protobuf,'extract',lambda x:SimpleNamespace(DESCRIPTOR=SimpleNamespace(name='ProtoOASpotEvent')))
    raw=dict(ctidTraderAccountId='12',symbolId='1',bid=110010,ask=110020,timestamp=int((T+timedelta(milliseconds=40)).timestamp()*1000))
    monkeypatch.setattr(module,'MessageToDict',lambda *a,**k:raw)
    binding.received(None,object())
    assert buffer.report()['pending']==1
    with pytest.raises(ValueError):binding._quote(T)
    now[0]+=timedelta(milliseconds=41);clock.advance(.041)
    assert buffer.report()['counts']['released']==1
    assert binding._quote(now[0]).observed_at==T+timedelta(milliseconds=40)
    # A new pending quote blocks even the earlier accepted quote.
    raw['timestamp']+=40;binding.received(None,object())
    with pytest.raises(ValueError):binding._quote(now[0])
    x.stream.disconnected();assert buffer.report()['pending']==0
    now[0]+=timedelta(seconds=1);clock.advance(1)
    with pytest.raises(ValueError):binding._quote(now[0])


def test_foreign_buffer_rejected(rig):
    with pytest.raises(ValueError,match='foreign quote buffer'):
        Binding(rig.session,rig.stream,rig.db,rig.bundle,approved_bundle_hash=rig.binding.pin,
                core_id='core',epoch=rig.epoch,now=lambda:T,spot_buffer=SimpleNamespace(stream=object()))


def test_preview_launcher_buffer_enabled_and_reported(setup):
    x=setup;x.args.quote_buffer_ms=100
    r=result(preview_launcher.run(x.clock,x.args,lambda:T))
    assert r['status']=='PREPARED_NOT_AUTHORIZED' and r['quote_buffer']['enabled']


def test_attended_shutdown_resets_pending_buffer(connected,monkeypatch):
    x,args,calls,events=connected;args.quote_buffer_ms=100;clock=task.Clock();saved=[]
    real=attended_launcher.assemble
    def assemble(*a,**kw):
        saved.append(kw['spot_buffer']);return real(*a,**kw)
    monkeypatch.setattr(attended_launcher,'assemble',assemble)
    def pending(*a,**kw):
        from twisted.internet import defer
        buffer=saved[0]
        buffer.on_spot(dict(ctidTraderAccountId='12',symbolId='1',bid=110010,ask=110020,
            timestamp=int((T+timedelta(milliseconds=40)).timestamp()*1000)))
        return defer.Deferred()
    monkeypatch.setattr(attended_launcher,'lifecycle',pending)
    d=attended_launcher.run(clock,args,lambda:T);d.cancel()
    assert result(d)['status']=='STOPPED_UNCONFIRMED'
    assert saved[0].report()['pending']==0
    clock.advance(1) # no callback touches the closed DB
    assert not calls
