import json
import stat
from datetime import timedelta
from types import SimpleNamespace
import pytest
from twisted.internet import defer, task
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader import attended_launcher as launch
from trading_platform.gateways.ctrader.settlement import CostPolicy
from test_modeled_risk import modeled, adapter, rig, result, T, H


@pytest.fixture
def config(modeled, tmp_path):
    x, a, calls, policy, bundle = modeled
    costs = CostPolicy(account_id='12',evidence_hash=H,verified_at=T,valid_until=T+timedelta(minutes=5),
        commission_sign='signed_cash',conversion_fee_sign='positive_charge',closing_commission_source='deal',
        closing_commission_excludes_opening=True,all_costs_covered=True)
    args = SimpleNamespace(account_id='12',execute=False,recover=False,output=tmp_path/'report',
        credentials='DO_NOT_READ',tokens='DO_NOT_READ',database=tmp_path/'db')
    for name,value in [('bundle',bundle),('proposal',x.entry),('review',a.report),('approval',a.approval),('cost_policy',costs)]:
        path=tmp_path/name;path.write_text(value.model_dump_json());setattr(args,name,path)
        if name!='proposal':setattr(args,'approved_'+name+'_hash',digest(value))
    return x,args,calls


def test_default_does_not_read_inputs_or_secrets(config,monkeypatch):
    x,args,calls=config
    def fail(*a):raise AssertionError('must not be called')
    monkeypatch.setattr(launch,'inputs',fail)
    r=result(launch.run(task.Clock(),args,lambda:T))
    assert r['status']=='DISABLED' and not calls and not args.database.exists()
    assert stat.S_IMODE(args.output.stat().st_mode)==0o600


@pytest.mark.parametrize('pin',['bundle','review','approval','cost_policy'])
def test_bad_pin_blocks_before_credentials(config,monkeypatch,pin):
    x,args,calls=config;args.execute=True;setattr(args,'approved_'+pin+'_hash','f'*64)
    touched=[];monkeypatch.setattr(launch,'TokenStore',lambda *a:touched.append(True))
    r=result(launch.run(task.Clock(),args,lambda:T))
    assert r['status']=='INPUT_OR_STARTUP_FAILED' and touched==[] and not calls


def test_expired_inputs_only_accepted_for_recovery(config):
    x,args,calls=config
    with pytest.raises(ValueError):launch.inputs(args,T+timedelta(minutes=6))
    args.recover=True
    assert launch.inputs(args,T+timedelta(minutes=6)).approval==launch.inputs(args,T).approval


def test_real_composition_disabled_and_single_consumed_entry(config):
    x,args,calls=config;data=launch.inputs(args,T)
    a,m=launch.assemble(x.session,x.stream,x.db,data,args,lambda:T)
    with pytest.raises(ValueError,match='disabled'):result(a.submit(x.entry))
    assert not calls and m.provider.contracts()=={}
    args.execute=True
    a,m=launch.assemble(x.session,x.stream,x.db,data,args,lambda:T)
    assert result(a.submit(x.entry))['status']=='AWAITING_RECONCILIATION'
    assert len(calls)==1
    with pytest.raises(ValueError,match='consumed'):result(a.submit(x.entry))


def test_recovery_without_attempt_never_repairs_or_submits(config):
    x,args,calls=config;args.execute=True;args.recover=True
    a,m=launch.assemble(x.session,x.stream,x.db,launch.inputs(args,T),args,lambda:T)
    r=result(launch.lifecycle(task.Clock(),x.session,x.stream,a,m,x.entry,recover=True))
    assert r['status']=='RECOVERY_REQUIRES_ATTEMPT' and not calls


def test_restart_refuses_new_entry_and_recovery_only_monitors(config):
    x,args,calls=config;args.execute=True
    a,m=launch.assemble(x.session,x.stream,x.db,launch.inputs(args,T),args,lambda:T)
    result(a.submit(x.entry))
    assert result(launch.lifecycle(task.Clock(),x.session,x.stream,a,m,x.entry,recover=False))['status']=='RECOVERY_REQUIRED'
    m.tick=lambda:defer.succeed(dict(status='TERMINAL_UNFILLED_COST_REVIEW_REQUIRED'))
    r=result(launch.lifecycle(task.Clock(),x.session,x.stream,a,m,x.entry,recover=True))
    assert not r['exposure_resolved'] and len(calls)==1


def test_lost_ack_enters_monitor_without_resend(config):
    x,args,calls=config;args.execute=True
    a,m=launch.assemble(x.session,x.stream,x.db,launch.inputs(args,T),args,lambda:T)
    x.stream.repair=lambda:defer.succeed(None)
    def lost(req,**kw):calls.append(req);raise TimeoutError('SECRET')
    x.client.send=lost
    m.tick=lambda:defer.succeed(dict(status='COMPLETE'))
    assert result(launch.lifecycle(task.Clock(),x.session,x.stream,a,m,x.entry,recover=False))['status']=='COMPLETE'
    assert len(calls)==1 and m._read(a.key)


@pytest.fixture
def connected(config,monkeypatch):
    x,args,calls=config;args.execute=True;events=[]
    monkeypatch.setattr(launch,'TokenStore',lambda *a:SimpleNamespace(read=lambda:events.append('credentials')))
    monkeypatch.setattr(launch,'Database',lambda *a:x.db)
    monkeypatch.setattr(launch,'VerifiedClient',lambda *a:x.client)
    monkeypatch.setattr(launch,'ReadOnlySession',lambda *a:x.session)
    monkeypatch.setattr(launch,'Stream',lambda *a:x.stream)
    x.client.startService=lambda:events.append('start')
    x.client.stopService=lambda:events.append('stop')
    # Fixture database is closed by launcher and its fixture; sqlite close is idempotent.
    return x,args,calls,events


def test_timeout_retires_paths_and_does_not_claim_flat(connected,monkeypatch):
    x,args,calls,events=connected;clock=task.Clock();saved=[]
    real=launch.assemble
    def assemble(*a,**kw):
        out=real(*a,**kw);saved.extend(out);return out
    monkeypatch.setattr(launch,'assemble',assemble)
    monkeypatch.setattr(launch,'lifecycle',lambda *a,**kw:defer.Deferred())
    pending=launch.run(clock,args,lambda:T);clock.advance(180)
    r=result(pending)
    assert r['status']=='STOPPED_UNCONFIRMED' and not r['exposure_resolved']
    assert not saved[0].enabled and not saved[0].gateway.authorized and not saved[1].enabled
    assert events==['credentials','start','stop'] and not x.session.ready
    x.client.received(None,object())


def test_cancelled_run_shuts_down(connected,monkeypatch):
    x,args,calls,events=connected
    monkeypatch.setattr(launch,'lifecycle',lambda *a,**kw:defer.Deferred())
    pending=launch.run(task.Clock(),args,lambda:T);pending.cancel()
    assert result(pending)['status']=='STOPPED_UNCONFIRMED' and events[-1]=='stop'


def test_output_refuses_overwrite(config):
    x,args,calls=config;args.output.write_text('preserve')
    with pytest.raises(FileExistsError):result(launch.run(task.Clock(),args,lambda:T))
    assert args.output.read_text()=='preserve' and not calls


def test_recovery_rejects_changed_broker_identity(config):
    x,args,calls=config;args.execute=True
    a,m=launch.assemble(x.session,x.stream,x.db,launch.inputs(args,T),args,lambda:T)
    x.raw['ProtoOATraderReq']['trader']['brokerName']='Different Broker'
    with pytest.raises(ValueError,match='identity mismatch'):
        result(m.provider.economics.collect())
    assert not calls


def test_secret_error_is_redacted(connected,monkeypatch):
    x,args,calls,events=connected
    def failed(*a,**kw):raise RuntimeError('SECRET_ACCESS_TOKEN')
    monkeypatch.setattr(launch,'lifecycle',failed)
    r=result(launch.run(task.Clock(),args,lambda:T))
    assert r['status']=='RECONCILIATION_REQUIRED' and not r['exposure_resolved']
    assert 'SECRET' not in args.output.read_text() and events[-1]=='stop'


def test_unconfirmed_client_stop_is_not_complete(connected,monkeypatch):
    x,args,calls,events=connected;clock=task.Clock()
    monkeypatch.setattr(launch,'lifecycle',lambda *a,**kw:defer.succeed(dict(status='COMPLETE',exposure_resolved=True)))
    x.client.stopService=lambda:defer.Deferred()
    pending=launch.run(clock,args,lambda:T);clock.advance(5)
    assert result(pending)['status']=='CLIENT_STOP_UNCONFIRMED'
