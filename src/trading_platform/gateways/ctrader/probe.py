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
def collect(session,now,symbols=('EURUSD','XAUUSD'),progress=None):
    at=now();generation=session.generation
    progress=progress or (lambda stage,evidence:None)
    profile=yield session.read('ProtoOATraderReq')
    if str(profile.get('ctidTraderAccountId'))!=str(session.account_id): raise ValueError('foreign trader profile')
    progress('ACCOUNT_PROFILE',profile)
    catalog=yield session.read('ProtoOASymbolsListReq',includeArchivedSymbols=False)
    if str(catalog.get('ctidTraderAccountId'))!=str(session.account_id): raise ValueError('foreign symbol catalog')
    progress('SYMBOL_CATALOG',catalog)
    selected={}
    for name in symbols:
        matches=[s for s in catalog.get('symbol',[]) if s.get('symbolName')==name]
        if len(matches)!=1: raise ValueError('explicit unique broker symbol required')
        selected[name]=int(matches[0]['symbolId'])
    metadata=yield session.read('ProtoOASymbolByIdReq',symbolId=list(selected.values()))
    if str(metadata.get('ctidTraderAccountId'))!=str(session.account_id): raise ValueError('foreign metadata')
    if {int(s['symbolId']) for s in metadata.get('symbol',[])}!=set(selected.values()): raise ValueError('incomplete metadata')
    progress('SYMBOL_METADATA',metadata)
    history={}
    start=at-timedelta(hours=24)
    for name,symbol in selected.items():
        history[name]=yield complete_range(session,'ProtoOAGetTrendbarsReq','trendbar',int(start.timestamp()*1000),int(at.timestamp()*1000),symbolId=symbol,period=1)
    progress('HISTORY',history)
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
        report['phase']='APPLICATION_AUTH_AND_DISCOVERY'
        accounts=yield discover(wire,store)
        if disconnected[0]: raise ValueError('discovery disconnected')
        account=args.account
        if account is None:
            if len(accounts)!=1:
                report.update(status='ACCOUNT_SELECTION_REQUIRED',reason='SELECT_EXPLICIT_DEMO_ACCOUNT',demo_account_ids=[str(a['ctidTraderAccountId']) for a in accounts])
                return
            account=str(accounts[0]['ctidTraderAccountId'])
        bind_demo(accounts,account)
        report['phase']='ACCOUNT_AUTH'
        session=Session(client,store,account)
        yield session.authenticate(session.generation,application_authenticated=True)
        report['account_id']=str(account)
        def progress(stage,evidence):
            report['phase']=stage
            report.setdefault('evidence',{})[stage]=evidence
        result=yield collect(session,lambda:datetime.now(timezone.utc),args.symbols,progress)
        if args.audit:
            from .audit import collect as audit
            result['capability_audit']=yield audit(session,result,lambda:datetime.now(timezone.utc))
        if getattr(args,'margin_audit',False):
            from .audit import collect_margins
            result['margin_audit']=yield collect_margins(session,result,lambda:datetime.now(timezone.utc))
        if getattr(args,'gap_start',None):
            from .gap_audit import collect as collect_gap
            result['gap_audit']=yield collect_gap(session,result['symbols'][args.gap_symbol],args.gap_start,lambda:datetime.now(timezone.utc))
        report=dict(result,status='COLLECTED')
    except Exception as error:
        # Only fixed local classifications are allowed into reports.
        known={'unsupported account margin profile':'UNSUPPORTED_MARGIN_PROFILE',
               'bonus valuation requires separate qualification':'UNQUALIFIED_BONUS',
               'stale account economics':'STALE_ACCOUNT_ECONOMICS',
               'account changed during valuation':'ACCOUNT_CHANGED_DURING_VALUATION',
               'explicit unique broker symbol required':'SYMBOL_SELECTION_REQUIRED'}
        report['reason']=known.get(str(error),'READONLY_QUALIFICATION_REQUIRED')
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
    p.add_argument('--audit',action='store_true')
    p.add_argument('--margin-audit',action='store_true')
    p.add_argument('--gap-start',help='Completed UTC minute to diagnose; no candle is synthesized')
    p.add_argument('--gap-symbol',choices=['EURUSD','XAUUSD'])
    args=p.parse_args()
    if bool(args.gap_start)!=bool(args.gap_symbol) or (args.gap_symbol and args.gap_symbol not in args.symbols):
        p.error('gap-start and gap-symbol must be supplied together for a selected symbol')
    if args.gap_start:
        from trading_platform.contracts.values import utc
        try:
            start=utc(args.gap_start);age=datetime.now(timezone.utc)-start
            if start.second or start.microsecond or not timedelta(minutes=1)<=age<=timedelta(days=7):raise ValueError()
        except (ValueError,TypeError):p.error('gap-start must identify a recent completed aligned minute')
    # Startup validation errors are intentionally generic.
    try: TokenStore(args.credentials,args.tokens).read()
    except Exception: raise SystemExit('Private application credentials and tokens are required.') from None
    task.react(lambda reactor:run(reactor,args))

if __name__=='__main__': main()
