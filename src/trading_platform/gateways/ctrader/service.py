"""Demo read-only collector process. No order transport is imported."""
import argparse,json,threading
from datetime import datetime,timezone,timedelta
from pathlib import Path
from twisted.internet import reactor,task,defer
from ctrader_open_api import Protobuf
from google.protobuf.json_format import MessageToDict
from trading_platform.persistence.database import Database
from trading_platform.market_data.service import Feed
from .auth import TokenStore
from .client import VerifiedClient,Session
from .readonly import Collector
from .stream import Stream
from .snapshot_server import Server


def main():
    parser=argparse.ArgumentParser()
    for name in ('credentials','tokens','account','state','feed-config','rpc-token'): parser.add_argument('--'+name,required=True)
    args=parser.parse_args();now=lambda:datetime.now(timezone.utc)
    config=json.loads(Path(args.feed_config).read_text())
    db=Database(args.state);client=VerifiedClient();session=Session(client,TokenStore(args.credentials,args.tokens),args.account)
    feed=Feed(db);stream=Stream(session,feed,config['symbols'],config['requirements'],now);collector=Collector(session,db,now)
    server=Server(("0.0.0.0",9100),Path(args.rpc_token).read_text().strip(),session,feed,config["requirements"])
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    busy=False
    def received(_client,message):
        payload=Protobuf.extract(message)
        if payload.DESCRIPTOR.name=='ProtoOASpotEvent':
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
            yield session.refresh_if_due()
            yield stream.repair()
            view=yield collector.collect(now()-timedelta(hours=config.get('history_hours',24)))
            print(json.dumps({'mode':'shadow','account_reconciled':view['history_complete'],'generation':session.generation,'orders_enabled':False}),flush=True)
        except Exception:
            stream.disconnected();print('{"mode":"shadow","ready":false,"reason":"RECONCILIATION_REQUIRED"}',flush=True)
        finally: busy=False
    loop=task.LoopingCall(poll);loop.start(10,now=False)
    def shutdown():
        server.shutdown();server.server_close();thread.join(5)
        if loop.running: loop.stop()
        result=client.stopService()
        if result is not None: result.addBoth(lambda _:db.close())
        else: db.close()
        return result
    reactor.addSystemEventTrigger('before','shutdown',shutdown)
    client.startService();reactor.run()

if __name__=='__main__': main()
