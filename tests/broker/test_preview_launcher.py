import json
import stat
from types import SimpleNamespace
import pytest
from twisted.internet import defer, task
from test_attended_binding import rig, result, T
from trading_platform.contracts.values import digest
from trading_platform.contracts.events import Quote
from trading_platform.gateways.ctrader import preview_launcher as launcher


@pytest.fixture
def setup(rig, tmp_path, monkeypatch):
    args=SimpleNamespace(bundle=tmp_path/'bundle',proposal=tmp_path/'entry',
        account_id='12',approved_bundle_hash=digest(rig.bundle),credentials='unused',
        tokens='unused',database=tmp_path/'database',output=tmp_path/'report')
    args.bundle.write_text(rig.bundle.model_dump_json())
    args.proposal.write_text(rig.entry.model_dump_json())
    calls=[]; clock=task.Clock()
    monkeypatch.setattr(launcher,'TokenStore',lambda *a:SimpleNamespace(read=lambda:calls.append('credentials')))
    monkeypatch.setattr(launcher,'VerifiedClient',lambda *a:rig.client)
    rig.client.startService=lambda:calls.append('start')
    rig.client.stopService=lambda:calls.append('stop')
    monkeypatch.setattr(launcher,'ReadOnlySession',lambda *a:rig.session)
    # Keep real Binding, Feed, Stream, Database and broker normalization.
    def repair(stream):
        stream.subscribed_generation=1
        stream.feed.repaired('EURUSD',T)
        stream.feed.ingest_quote(Quote(
            instrument='EURUSD',bid='1.1001',ask='1.1002',source_time=T,received_at=T))
        return defer.succeed(None)
    monkeypatch.setattr(launcher.Stream,'repair',repair)
    return SimpleNamespace(args=args,calls=calls,clock=clock,rig=rig)


def test_connected_composition_with_real_binding(setup):
    x=setup; report=result(launcher.run(x.clock,x.args,lambda:T))
    assert report['status']=='PREPARED_NOT_AUTHORIZED'
    assert x.calls==['credentials','start','stop']
    assert json.loads(x.args.output.read_text())['orders_enabled'] is False
    assert stat.S_IMODE(x.args.output.stat().st_mode)==0o600
    assert not x.rig.session.ready and x.rig.session.demo_binding is None
    db=launcher.Database(x.args.database);db.close() # lock released


def test_missing_review_never_accesses_credentials(setup):
    x=setup;x.args.bundle.unlink()
    report=result(launcher.run(x.clock,x.args,lambda:T))
    assert report['blockers']==['REVIEW_REQUIRED'] and x.calls==[]


def test_existing_output_is_untouched(setup):
    x=setup;x.args.output.write_text('keep')
    with pytest.raises(FileExistsError):result(launcher.run(x.clock,x.args,lambda:T))
    assert x.args.output.read_text()=='keep' and x.calls==[]


def test_authentication_timeout_stops_and_closes(setup):
    x=setup;x.rig.session.ready=False
    pending=launcher.run(x.clock,x.args,lambda:T)
    x.clock.advance(30)
    assert result(pending)['reason']=='PREVIEW_TIMEOUT'
    assert x.calls[-1]=='stop'
    db=launcher.Database(x.args.database);db.close()


def test_failure_is_redacted_and_cleaned(setup,monkeypatch):
    x=setup
    def fail(*a):raise ValueError('SECRET')
    monkeypatch.setattr(launcher,'collect',fail)
    assert result(launcher.run(x.clock,x.args,lambda:T))['reason']=='READONLY_PREVIEW_FAILED'
    assert 'SECRET' not in x.args.output.read_text() and x.calls[-1]=='stop'


def test_stop_timeout_does_not_report_success(setup):
    x=setup;x.rig.client.stopService=lambda:defer.Deferred()
    pending=launcher.run(x.clock,x.args,lambda:T);x.clock.advance(5)
    assert result(pending)['reason']=='CLIENT_STOP_UNCONFIRMED'


def test_reconnect_during_quote_wait_fails(rig):
    clock=task.Clock();rig.feed.invalidate_quote('EURUSD')
    rig.stream.repair=lambda:defer.succeed(None)
    pending=launcher.collect(clock,rig.session,rig.stream,rig.binding,rig.entry)
    rig.session.generation+=1;clock.advance(.05)
    with pytest.raises(ValueError,match='connection changed'):result(pending)


def test_quote_timeout_retires_callback_before_storage_close(setup,monkeypatch):
    x=setup
    def empty_repair(stream):
        stream.subscribed_generation=1
        stream.feed.repaired('EURUSD',T)
        return defer.succeed(None)
    monkeypatch.setattr(launcher.Stream,'repair',empty_repair)
    pending=launcher.run(x.clock,x.args,lambda:T)
    x.clock.advance(30)
    assert result(pending)['reason']=='PREVIEW_TIMEOUT'
    x.rig.client.received(None,object()) # detached; never accesses closed database
    assert x.calls[-1]=='stop'


def test_credential_failure_writes_private_redacted_report(setup,monkeypatch):
    x=setup
    def fail(*a):raise ValueError('SECRET')
    monkeypatch.setattr(launcher,'TokenStore',fail)
    assert result(launcher.run(x.clock,x.args,lambda:T))['reason']=='READONLY_PREVIEW_FAILED'
    assert x.calls==[] and 'SECRET' not in x.args.output.read_text()
