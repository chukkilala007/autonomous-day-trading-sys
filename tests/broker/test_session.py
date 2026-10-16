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
