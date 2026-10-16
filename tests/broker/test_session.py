import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.defer import succeed
from trading_platform.gateways.ctrader.client import Session, VerifiedClient, HOST


class Client:
    def setConnectedCallback(self,cb): self.connected=cb
    def setDisconnectedCallback(self,cb): self.disconnected=cb
    def stopService(self): self.stopped=True


class Tokens:
    def read(self): return dict(client_id='synthetic',client_secret='secret-test',access_token='token-test',refresh_token='refresh-test',expires_at=1000)


def test_session_reauth_read_allowlist_and_stale_generation():
    client=Client();session=Session(client,Tokens(),12,now=lambda:1);sent=[]
    def wire(name,**fields):
        sent.append((name,fields))
        return succeed({'ctidTraderAccount':[{'ctidTraderAccountId':'12','isLive':False}]} if name=='ProtoOAGetAccountListByAccessTokenReq' else {'ctidTraderAccountId':'12'})
    session.wire=wire;client.connected()
    assert session.ready and len(sent)==3
    with pytest.raises(ValueError): session.read('ProtoOANewOrderReq')
    with pytest.raises(ValueError): session.read('ProtoOATraderReq',ctidTraderAccountId=999)
    session.read('ProtoOATraderReq');assert sent[-1][1]['ctidTraderAccountId']==12
    client.disconnected();assert not session.ready
    client.connected();assert session.ready and session.generation==3
    failure=[];session.authenticate(1).addErrback(lambda e:failure.append(e))
    assert failure


def test_sdk_uses_verified_demo_tls_and_private_queues(monkeypatch):
    from trading_platform.gateways.ctrader import client as module
    captured=[]
    endpoint=module.SSL4ClientEndpoint
    def record(clock,host,port,context,**kwargs):
        captured.append((host,port,context))
        return endpoint(clock,host,port,context,**kwargs)
    monkeypatch.setattr(module,'SSL4ClientEndpoint',record)
    VerifiedClient()
    assert captured[0][:2]==(HOST,5035)
    assert captured[0][2]._hostnameASCII==HOST


def test_failed_refresh_stops_client_and_exposes_terminal_state():
    from twisted.internet.defer import fail
    client=Client();session=Session(client,Tokens(),12,now=lambda:1000)
    session.ready=True
    session.authenticate=lambda generation:fail(ValueError('sensitive broker detail'))
    errors=[];session.refresh_if_due().addErrback(lambda error:errors.append(error))
    assert errors and str(errors[0].value)=='authentication refresh failed'
    assert not session.ready and session.error=='AUTHENTICATION_FAILED' and client.stopped


def test_discovered_connection_skips_duplicate_application_auth_but_reconnect_does_not():
    client=Client();session=Session(client,Tokens(),12,now=lambda:1);sent=[]
    def wire(name,**fields):
        sent.append(name)
        return succeed({'ctidTraderAccount':[{'ctidTraderAccountId':'12','isLive':False}]} if name=='ProtoOAGetAccountListByAccessTokenReq' else {'ctidTraderAccountId':'12'})
    session.wire=wire
    session.authenticate(session.generation,application_authenticated=True)
    assert session.ready and sent==['ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq']
    sent.clear();client.disconnected();client.connected()
    assert session.ready and sent==['ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq']


def test_sdk_request_pacing_stays_below_historical_limit(monkeypatch):
    from twisted.internet import task
    from types import SimpleNamespace
    from trading_platform.gateways.ctrader.client import IsolatedProtocol
    clock=task.Clock();original=task.LoopingCall
    def looping(*args,**kwargs):
        loop=original(*args,**kwargs);loop.clock=clock;return loop
    monkeypatch.setattr(task,'LoopingCall',looping)
    protocol=IsolatedProtocol();sent=[]
    protocol.factory=SimpleNamespace(numberOfMessagesToSendPerSecond=1,connected=lambda _:None,disconnected=lambda _:None)
    protocol.sendString=lambda data:sent.append((clock.seconds(),data))
    protocol.connectionMade();sent.clear()
    for i in range(8):protocol.send(bytes([i]))
    for _ in range(8):clock.advance(.26)
    assert len(sent)==8
    assert all(abs(sent[i][0]-(i+1)*.26)<1e-8 for i in range(8))
    protocol.connectionLost(None)
    assert not protocol._send_task.running


def test_readonly_wire_rejects_mutations_even_without_read_helper():
    from trading_platform.gateways.ctrader.read_only_session import ReadOnlySession
    session=ReadOnlySession(Client(),Tokens(),12)
    for name in ('ProtoOANewOrderReq','ProtoOACancelOrderReq','ProtoOAClosePositionReq','ProtoOAAmendPositionSLTPReq'):
        with pytest.raises(ValueError,match='read-only wire'):session.wire(name)
    assert session.rejected_writes==4 and not session.requests


def test_readonly_report_separates_reconnect_and_fresh_coverage():
    from trading_platform.gateways.ctrader.read_only_session import summarize
    metrics=dict(reconnect_requested=True,disconnects=1,reconciled_generations=[1,3],complete_snapshots=0,reconciliations=4)
    report=summarize(metrics,{'ProtoOAReconcileReq':4},0,reconnect_required=True)
    assert report['reconnect_status']=='PASS' and report['status']=='BLOCKED_FRESH_COVERAGE' and report['order_writes']==0
    metrics['complete_snapshots']=1
    assert summarize(metrics,{},0,reconnect_required=True)['status']=='PASS'
    metrics['reconciled_generations']=[1]
    assert summarize(metrics,{},0,reconnect_required=True)['status']=='BLOCKED_RECONNECT'
    assert summarize(metrics,{'ProtoOANewOrderReq':1},0,reconnect_required=True)['status']=='FAILED_READONLY_BOUNDARY'
