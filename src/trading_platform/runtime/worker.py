import argparse,json,socketserver
from pathlib import Path
from .transport import receive,send,authorize
from .scheduler import evaluate
from trading_platform.registry.loader import Registry
from trading_platform.registry.manifest import Manifest
from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Event
from trading_platform.contracts.snapshots import Snapshot


class Server(socketserver.TCPServer):
    allow_reuse_address=True
    def __init__(self,address,token,instance_id,registry=None):
        if len(token)<32: raise ValueError('token must have at least 32 characters')
        self.token=token;self.instance_id=instance_id;self.registry=registry or Registry({})
        super().__init__(address,Handler)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        msg={}
        try:
            msg=receive(self.request)
            authorize(msg,self.server.token,self.server.instance_id)
            body=msg['body']
            if body['op']=='ping': result={'healthy':True}
            elif body['op']=='evaluate':
                instance=Instance.model_validate_json(json.dumps(body['instance']))
                if instance.instance_id!=self.server.instance_id: raise ValueError('wrong instance')
                registry=self.server.registry
                if instance.instance_id not in registry.instances: registry.load(instance)
                bound,manifest,plugin=registry.instances[instance.instance_id]
                if instance.hash!=bound.hash: raise ValueError('instance configuration changed')
                snapshot=Snapshot.model_validate_json(json.dumps(body['snapshot']))
                event=Event.model_validate_json(json.dumps(body['event']))
                out=evaluate(plugin,manifest,instance,event,snapshot,tuple(body.get('portfolio',())),body['state'])
                for d in out.decisions:
                    if d.proposal: plugin.validate_proposal(d.proposal,snapshot)
                result=json.loads(out.model_dump_json())
            else: raise ValueError('unsupported operation')
            send(self.request,{'request_id':msg['request_id'],'body':result})
        except (ValueError,KeyError,TypeError,TimeoutError) as exc:
            try: send(self.request,{'request_id':msg.get('request_id'),'error':type(exc).__name__+': '+str(exc)})
            except OSError: pass


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=9000)
    p.add_argument('--instance',required=True);p.add_argument('--token-file',required=True)
    p.add_argument('--registry');args=p.parse_args()
    manifests=[] if not args.registry else json.loads(Path(args.registry).read_text())
    reviewed={m['package']:Manifest.model_validate_json(json.dumps(m)) for m in manifests}
    with Server(('0.0.0.0',args.port),Path(args.token_file).read_text().strip(),args.instance,Registry(reviewed)) as server:
        server.serve_forever()

if __name__=='__main__': main()
