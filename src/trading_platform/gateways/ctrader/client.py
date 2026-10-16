"""Pinned SDK adapter; verified TLS, reconnect authentication, read-only allowlist."""
from collections import deque
import time
from twisted.application.internet import ClientService, backoffPolicy
from twisted.internet import reactor, defer
from twisted.internet.endpoints import SSL4ClientEndpoint
from twisted.internet.ssl import optionsForClientTLS
from ctrader_open_api import Client, TcpProtocol, Protobuf
from ctrader_open_api.factory import Factory
from google.protobuf.json_format import MessageToDict
from .auth import bind_demo

HOST = 'demo.ctraderapi.com'
READ_REQUESTS = frozenset(('ProtoOATraderReq','ProtoOASymbolsListReq','ProtoOASymbolByIdReq','ProtoOAAssetListReq',
    'ProtoOAReconcileReq','ProtoOADealListReq','ProtoOAOrderListReq','ProtoOAGetTrendbarsReq','ProtoOAGetTickDataReq',
    'ProtoOASubscribeSpotsReq','ProtoOAUnsubscribeSpotsReq','ProtoOASubscribeLiveTrendbarReq',
    'ProtoOAUnsubscribeLiveTrendbarReq','ProtoOAExpectedMarginReq','ProtoOASymbolsForConversionReq','ProtoOAGetPositionUnrealizedPnLReq'))


class IsolatedProtocol(TcpProtocol):
    def connectionMade(self):
        self._send_queue=deque(); self._send_task=None; self._lastSendMessageTime=None
        super().connectionMade()


class VerifiedClient(Client):
    def __init__(self, clock=reactor):
        self._runningReactor=clock; self.numberOfMessagesToSendPerSecond=4
        endpoint=SSL4ClientEndpoint(clock,HOST,5035,optionsForClientTLS(HOST),timeout=10)
        ClientService.__init__(self,endpoint,Factory.forProtocol(IsolatedProtocol,client=self),retryPolicy=backoffPolicy(initialDelay=1,maxDelay=60))
        self._events={}; self._responseDeferreds={}; self.isConnected=False

    def stopService(self):
        return ClientService.stopService(self)


class Session:
    def __init__(self, client, tokens, account_id, now=time.time):
        if not str(account_id).isdigit() or int(account_id)<=0: raise ValueError('explicit account ID required')
        self.client=client; self.tokens=tokens; self.account_id=int(account_id); self.now=now
        self.ready=False; self.error=None; self.generation=0; self.authenticated=None
        client.setConnectedCallback(self.connected)
        client.setDisconnectedCallback(self.disconnected)

    @defer.inlineCallbacks
    def wire(self, name, **fields):
        from ctrader_open_api.messages import OpenApiMessages_pb2 as messages
        request=getattr(messages,name)(**fields)
        response=yield self.client.send(request,responseTimeoutInSeconds=10)
        payload=Protobuf.extract(response)
        if payload.DESCRIPTOR.name != name.replace('Req','Res'):
            raise ValueError('broker request rejected or unexpected response')
        return MessageToDict(payload,preserving_proto_field_name=True)

    def disconnected(self, *_):
        self.ready=False; self.generation+=1; self.error='DISCONNECTED'

    def connected(self, *_):
        self.ready=False; self.generation+=1
        self.authenticated=self.authenticate(self.generation)
        self.authenticated.addErrback(self.failed)

    def failed(self, _failure):
        # Broker error descriptions and auth payloads can contain secrets.
        self.ready=False; self.error='AUTHENTICATION_FAILED'
        self.client.stopService()
        return None

    @defer.inlineCallbacks
    def authenticate(self, generation, *, application_authenticated=False):
        credentials=self.tokens.read()
        if not application_authenticated:
            yield self.wire('ProtoOAApplicationAuthReq',clientId=credentials['client_id'],clientSecret=credentials['client_secret'])
        if credentials['expires_at'] <= self.now()+60:
            response=yield self.wire('ProtoOARefreshTokenReq',refreshToken=credentials['refresh_token'])
            credentials=self.tokens.rotate(credentials,response,self.now())
        accounts=yield self.wire('ProtoOAGetAccountListByAccessTokenReq',accessToken=credentials['access_token'])
        bind_demo(accounts.get('ctidTraderAccount',[]),self.account_id)
        response=yield self.wire('ProtoOAAccountAuthReq',ctidTraderAccountId=self.account_id,accessToken=credentials['access_token'])
        if str(response.get('ctidTraderAccountId'))!=str(self.account_id): raise ValueError('account authentication mismatch')
        if generation != self.generation: raise ValueError('stale authentication')
        self.ready=True; self.error=None

    @defer.inlineCallbacks
    def refresh_if_due(self):
        if not self.ready: raise ValueError("account not ready")
        try:
            if self.tokens.read()["expires_at"] <= self.now()+60:
                self.ready=False
                yield self.authenticate(self.generation)
        except Exception:
            self.failed(None)
            raise ValueError("authentication refresh failed") from None

    def read(self, name, **fields):
        if name not in READ_REQUESTS: raise ValueError('read-only gateway rejects operation')
        if not self.ready: raise ValueError('account not ready')
        if 'ctidTraderAccountId' in fields: raise ValueError('account binding cannot be overridden')
        return self.wire(name,ctidTraderAccountId=self.account_id,**fields)
