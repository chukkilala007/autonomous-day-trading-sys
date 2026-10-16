"""Bounded demo discovery/read-only evidence collection. No order transport.

Private report includes account records, never authentication payloads. A probe
is evidence collection, not full capability/shadow/execution qualification.
"""
import argparse,json,os,time
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from twisted.internet import defer,task
from trading_platform.contracts.values import canonical,digest
from .auth import TokenStore,bind_demo
from .client import VerifiedClient,Session,HOST
from .economics import EconomicsCollector
from .history import complete_range


@defer.inlineCallbacks
def discover(wire,store,now=time.time):
    credentials=store.read()
    yield wire('ProtoOAApplicationAuthReq',clientId=credentials['client_id'],clientSecret=credentials['client_secret'])
    if credentials['expires_at']<=now()+60:
        refreshed=yield wire('ProtoOARefreshTokenReq',refreshToken=credentials['refresh_token'])
        credentials=store.rotate(credentials,refreshed,now())
    response=yield wire('ProtoOAGetAccountListByAccessTokenReq',accessToken=credentials['access_token'])
    accounts=response.get('ctidTraderAccount',[])
    identities=[str(a['ctidTraderAccountId']) for a in accounts]
    if len(identities)!=len(set(identities)): raise ValueError('duplicate account discovery')
    return [a for a in accounts if a.get('isLive') is False]


@defer.inlineCallbacks
def collect(session,now,symbols=('EURUSD','XAUUSD')):
    at=now();generation=session.generation
    catalog=yield session.read('ProtoOASymbolsListReq',includeArchivedSymbols=False)
    if str(catalog.get('ctidTraderAccountId'))!=str(session.account_id): raise ValueError('foreign symbol catalog')
    selected={}
    for name in symbols:
        matches=[s for s in catalog.get('symbol',[]) if s.get('symbolName')==name]
        if len(matches)!=1: raise ValueError('explicit unique broker symbol required')
        selected[name]=int(matches[0]['symbolId'])
    metadata=yield session.read('ProtoOASymbolByIdReq',symbolId=list(selected.values()))
    if str(metadata.get('ctidTraderAccountId'))!=str(session.account_id): raise ValueError('foreign metadata')
    if {int(s['symbolId']) for s in metadata.get('symbol',[])}!=set(selected.values()): raise ValueError('incomplete metadata')
    history={}
    start=at-timedelta(hours=24)
    for name,symbol in selected.items():
        history[name]=yield complete_range(session,'ProtoOAGetTrendbarsReq','trendbar',int(start.timestamp()*1000),int(at.timestamp()*1000),symbolId=symbol,period=1)
    economics=yield EconomicsCollector(session,now).collect()
    if session.generation!=generation or not session.ready: raise ValueError('connection changed during probe')
    payload=dict(format=1,mode='demo-readonly',host=HOST,orders_enabled=False,account_id=str(session.account_id),
                 collected_at=now().isoformat(),symbols=selected,metadata=metadata,economics=economics,
                 history_from=start.isoformat(),history_to=at.isoformat(),trendbars=history,
                 qualification_complete=False,remaining=['verified candle basis and live session','contract conversion and cost mapping','streaming/reconnect shadow run','actual demo execution acceptance'])
    payload['evidence_hash']=digest(payload)
    return payload


@defer.inlineCallbacks
def run(reactor,args):
    # Reserve a private report destination before touching authentication.
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    store=TokenStore(args.credentials,args.tokens);store.read()
    client=VerifiedClient(reactor);connected=defer.Deferred();disconnected=[False]
    client.setConnectedCallback(lambda *_:connected.callback(None) if not connected.called else None)
    def lost(*_): disconnected[0]=True
    client.setDisconnectedCallback(lost)
    client.startService()
    report=dict(format=1,mode='demo-readonly',orders_enabled=False,status='FAILED',reason='READONLY_QUALIFICATION_REQUIRED')
    try:
        yield connected.addTimeout(20,reactor)
        wire=lambda name,**fields:Session.wire(SimpleNamespace(client=client),name,**fields)
        accounts=yield discover(wire,store)
        if disconnected[0]: raise ValueError('discovery disconnected')
        account=args.account
        if account is None:
            if len(accounts)!=1:
                report.update(status='ACCOUNT_SELECTION_REQUIRED',demo_account_ids=[str(a['ctidTraderAccountId']) for a in accounts])
                return
            account=str(accounts[0]['ctidTraderAccountId'])
        bind_demo(accounts,account)
        session=Session(client,store,account)
        yield session.authenticate(session.generation)
        result=yield collect(session,lambda:datetime.now(timezone.utc),args.symbols)
        report=dict(result,status='COLLECTED')
    except Exception:
        # Broker descriptions and SDK failures can contain credentials.
        pass
    finally:
        yield defer.maybeDeferred(client.stopService)
        with os.fdopen(fd,'w') as output:
            output.write(canonical(report)+'\n');output.flush();os.fsync(output.fileno())
        print(json.dumps({'status':report['status'],'orders_enabled':False,'report_written':True}),flush=True)
    if report['status']=='FAILED': raise SystemExit(1)


def main():
    p=argparse.ArgumentParser()
    for name in ('credentials','tokens','output'): p.add_argument('--'+name,required=True)
    p.add_argument('--account');p.add_argument('--symbols',nargs='+',default=['EURUSD','XAUUSD'])
    args=p.parse_args()
    # Startup validation errors are intentionally generic.
    try: TokenStore(args.credentials,args.tokens).read()
    except Exception: raise SystemExit('Private application credentials and tokens are required.') from None
    task.react(lambda reactor:run(reactor,args))

if __name__=='__main__': main()
