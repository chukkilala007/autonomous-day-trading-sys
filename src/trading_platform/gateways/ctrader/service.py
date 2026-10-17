"""Demo read-only collector process. No order transport is imported."""
import argparse,json,threading,os
from datetime import datetime,timezone,timedelta
from pathlib import Path
from twisted.internet import reactor,task,defer
from ctrader_open_api import Protobuf
from google.protobuf.json_format import MessageToDict
from trading_platform.persistence.database import Database
from trading_platform.market_data.service import Feed
from .auth import TokenStore
from .client import VerifiedClient
from .read_only_session import ReadOnlySession as Session,summarize
from .readonly import Collector
from .stream import Stream
from .snapshot_server import Server
from .feed_config import validate as validate_feed
from .metadata import CapabilityReport


def main():
    parser=argparse.ArgumentParser()
    for name in ('credentials','tokens','account','state','feed-config','rpc-token'): parser.add_argument('--'+name,required=True)
    parser.add_argument('--run-seconds',type=int,default=0)
    parser.add_argument('--reconnect-after',type=int,default=0)
    parser.add_argument('--report')
    args=parser.parse_args();now=lambda:datetime.now(timezone.utc)
    if args.run_seconds<0 or args.reconnect_after<0 or (args.reconnect_after and not 0<args.reconnect_after<args.run_seconds):
        parser.error('reconnect drill requires a bounded run')
    report_fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600) if args.report else None
    config=json.loads(Path(args.feed_config).read_text())
    validate_feed(config,args.account,now())
    db=Database(args.state);client=VerifiedClient();session=Session(client,TokenStore(args.credentials,args.tokens),args.account)
    feed=Feed(db);stream=Stream(session,feed,config['symbols'],config['requirements'],now);collector=Collector(session,db,now)
    server=Server(("0.0.0.0",9100),Path(args.rpc_token).read_text().strip(),session,feed,config["requirements"])
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    busy=False;active=None
    metrics=dict(mode='shadow',orders_enabled=False,started_at=now().isoformat(),reconciliations=0,complete_snapshots=0,spot_events=0,disconnects=0,reconnect_requested=False,failures=0,reconciled_generations=[])
    def disconnected(*args):
        session.disconnected(*args);stream.disconnected();metrics['disconnects']+=1
    client.setDisconnectedCallback(disconnected)
    def received(_client,message):
        payload=Protobuf.extract(message)
        if payload.DESCRIPTOR.name=='ProtoOASpotEvent' and session.ready:
            metrics['spot_events']+=1
            try: stream.on_spot(MessageToDict(payload,preserving_proto_field_name=True))
            except ValueError: stream.disconnected()
    client.setMessageReceivedCallback(received)
    @defer.inlineCallbacks
    def poll():
        nonlocal busy
        if busy: return
        if not session.ready:
            stream.disconnected()
            if session.error=='AUTHENTICATION_FAILED': reactor.stop()
            return
        busy=True
        try:
            validate_feed(config,args.account,now())
            yield session.refresh_if_due()
            yield stream.repair()
            view=yield collector.collect(now()-timedelta(hours=config.get('history_hours',24)))
            metrics['reconciliations']+=1
            if session.generation not in metrics['reconciled_generations']:metrics['reconciled_generations'].append(session.generation)
            complete=feed.snapshot(now(),config['requirements']).coverage_complete
            metrics['complete_snapshots']+=int(complete)
            reports={name:CapabilityReport.model_validate_json(json.dumps(raw)) for name,raw in config['reports'].items()}
            feed.put('operations:provider',dict(connection_state='CONNECTED',generation=session.generation,coverage_complete=complete,observed_at=now(),source='actual_demo_readonly',capability_blockers={name:r.blockers(now(),str(session.account_id),name) for name,r in reports.items()}))
            print(json.dumps({'mode':'shadow','account_reconciled':view['history_complete'],'coverage_complete':complete,'generation':session.generation,'orders_enabled':False}),flush=True)
        except Exception:
            metrics['failures']+=1
            stream.disconnected();print('{"mode":"shadow","ready":false,"reason":"RECONCILIATION_REQUIRED"}',flush=True)
        finally: busy=False
    def cycle():
        nonlocal active
        active=poll();return active
    loop=task.LoopingCall(cycle);loop.start(10,now=False)
    def reconnect():
        if not session.ready:return
        metrics['reconnect_requested']=True
        # Deliberately break this read-only TCP connection; SDK reconnects/authenticates.
        client.whenConnected().addCallback(lambda protocol:protocol.transport.abortConnection())
    if args.reconnect_after:reactor.callLater(args.reconnect_after,reconnect)
    if args.run_seconds:reactor.callLater(args.run_seconds,reactor.stop)
    @defer.inlineCallbacks
    def shutdown():
        if loop.running: loop.stop()
        if active is not None and not active.called:
            try:yield active.addTimeout(20,reactor)
            except Exception:metrics['failures']+=1
        # Snapshot server is read-only, and its thread is joined before database close.
        server.shutdown();server.server_close();thread.join(5)
        metrics['cached_bars']=db.connection.execute("SELECT count(*) FROM checkpoints WHERE id LIKE 'bar:%'").fetchone()[0]
        metrics['quote_sources']={symbol:(feed.get('quote:'+symbol) or {}).get('source_time') for symbol in config['symbols']}
        metrics.update(ended_at=now().isoformat(),generation=session.generation)
        metrics.update(summarize(metrics,session.requests,session.rejected_writes,reconnect_required=bool(args.reconnect_after)))
        yield defer.maybeDeferred(client.stopService)
        if report_fd is not None:
            with os.fdopen(report_fd,'w') as output:
                json.dump(metrics,output,sort_keys=True);output.write('\n');output.flush();os.fsync(output.fileno())
        db.close()
    reactor.addSystemEventTrigger('before','shutdown',shutdown)
    client.startService();reactor.run()

if __name__=='__main__': main()
