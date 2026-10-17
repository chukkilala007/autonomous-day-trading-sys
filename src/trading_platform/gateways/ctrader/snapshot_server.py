"""Authenticated read-only snapshot port; no order mutation handlers exist."""
import json,socketserver
from datetime import datetime,timezone
from trading_platform.runtime.transport import receive,send,authorize
from trading_platform.contracts.values import utc


class Server(socketserver.TCPServer):
    allow_reuse_address=True
    def __init__(self,address,token,session,feed,requirements,now=None):
        if len(token)<32: raise ValueError('strong snapshot token required')
        self.token=token;self.session=session;self.feed=feed;self.requirements=requirements
        self.now=now or (lambda:datetime.now(timezone.utc))
        super().__init__(address,Handler)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5);message={}
        try:
            message=receive(self.request);authorize(message,self.server.token,'shadow-core')
            if message['body'].get('op')!='snapshot': raise ValueError('read-only snapshot operation required')
            if not self.server.session.ready: raise ValueError('broker not ready')
            with self.server.feed.db.mutex:
                at=self.server.now();account=self.server.feed.get('shadow:account')
                if not account or not 0<=(at-utc(account['observed_at'])).total_seconds()<=30: raise ValueError('stale account view')
                snapshot=self.server.feed.snapshot(at,self.server.requirements)
                result={'snapshot':json.loads(snapshot.model_dump_json()),'account':account,'source':'actual_demo_readonly','provider':self.server.feed.get('operations:provider') or {}}
            send(self.request,{'request_id':message['request_id'],'body':result})
        except (ValueError,KeyError,TypeError):
            send(self.request,{'request_id':message.get('request_id'),'error':'READONLY_SNAPSHOT_UNAVAILABLE'})
