"""Private authenticated demo RPC boundary.

Production hosts must marshal dispatch onto the SDK reactor with
blockingCallFromThread; the request thread never uses the SDK directly.
No command-line launcher or enabled broker deployment is provided here.
"""
import socketserver
from trading_platform.runtime.transport import receive,send,authorize


class Server(socketserver.TCPServer):
    allow_reuse_address=True
    def __init__(self,address,token,dispatch):
        if len(token)<32: raise ValueError('private strong demo RPC token required')
        self.token=token;self.dispatch=dispatch
        super().__init__(address,Handler)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(15);message={}
        try:
            message=receive(self.request);authorize(message,self.server.token,'demo-core')
            if not isinstance(message.get('body'),dict): raise ValueError('invalid request')
            result=self.server.dispatch(message['body'])
            send(self.request,{'request_id':message['request_id'],'body':result})
        except (ValueError,KeyError,TypeError,OSError,TimeoutError):
            try: send(self.request,{'request_id':message.get('request_id'),'error':'DEMO_OPERATION_REQUIRES_RECONCILIATION'})
            except OSError: pass


def reactor_server(address,token,api,reactor):
    from twisted.internet.threads import blockingCallFromThread
    return Server(address,token,lambda body:blockingCallFromThread(reactor,api.handle,body))
