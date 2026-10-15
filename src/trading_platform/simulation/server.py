"""Private-network simulator process; never connects to a real broker."""
import argparse,json,socketserver
from pathlib import Path
from trading_platform.runtime.transport import receive,send,authorize,request
from trading_platform.contracts.events import Quote
from trading_platform.contracts.values import utc
from trading_platform.execution.state_machine import BrokerEvent
from .broker import PaperBroker


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10);msg={}
        try:
            msg=receive(self.request);authorize(msg,self.server.token,'paper-broker')
            b=msg['body'];broker=self.server.broker;op=b['op']
            if op=='ping': result={'healthy':True}
            elif op=='events': result=[json.loads(e.model_dump_json()) for e in broker.events()]
            elif op=='management_confirmed': result=broker.management_confirmed(b['id'])
            elif op=='account': result=broker.account()
            elif op in ('submit','tick','manage'):
                now=utc(b['now'])
                if op=='manage': events=broker.manage(b['command'],now,b.get('fault'))
                else:
                    q=Quote.model_validate_json(json.dumps(b['quote']))
                    events=broker.submit(b['command'],q,now,b.get('fault')) if op=='submit' else broker.tick(q,now)
                result=[json.loads(e.model_dump_json()) for e in events]
            else: raise ValueError('unsupported operation')
            send(self.request,{'request_id':msg['request_id'],'body':result})
        except (ValueError,KeyError,TimeoutError,OSError) as exc:
            try: send(self.request,{'request_id':msg.get('request_id'),'error':type(exc).__name__+': '+str(exc)})
            except OSError: pass


class RemoteBroker:
    def __init__(self,host,port,token): self.host=host;self.port=port;self.token=token
    def call(self,op,**kwargs):
        try: return request(self.host,self.port,self.token,'paper-broker',{'op':op}|kwargs)
        except ValueError as exc:
            if str(exc).startswith(('TimeoutError:','OSError:')): raise TimeoutError(str(exc)) from exc
            raise
    def events(self): return [BrokerEvent.model_validate_json(json.dumps(e)) for e in self.call('events')]
    def management_confirmed(self,id): return self.call('management_confirmed',id=id)
    def account(self): return self.call('account')
    def submit(self,cmd,q,now): return [BrokerEvent.model_validate_json(json.dumps(e)) for e in self.call('submit',command=cmd,quote=json.loads(q.model_dump_json()),now=now.isoformat())]
    def tick(self,q,now): return [BrokerEvent.model_validate_json(json.dumps(e)) for e in self.call('tick',quote=json.loads(q.model_dump_json()),now=now.isoformat())]
    def manage(self,cmd,now): return [BrokerEvent.model_validate_json(json.dumps(e)) for e in self.call('manage',command=cmd,now=now.isoformat())]


def main():
    p=argparse.ArgumentParser();p.add_argument('--state',required=True);p.add_argument('--token-file',required=True);p.add_argument('--port',type=int,default=9000);args=p.parse_args()
    socketserver.TCPServer.allow_reuse_address=True
    with socketserver.TCPServer(('0.0.0.0',args.port),Handler) as server:
        server.token=Path(args.token_file).read_text().strip();server.broker=PaperBroker(args.state)
        server.serve_forever()

if __name__=='__main__': main()
