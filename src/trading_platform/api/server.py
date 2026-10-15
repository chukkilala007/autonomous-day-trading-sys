import hmac,json,threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .status import status


class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,db,reader_token,operator_token=None):
        if len(reader_token)<32 or (operator_token is not None and len(operator_token)<32): raise ValueError('strong API tokens required')
        if reader_token==operator_token: raise ValueError('separate API roles required')
        self.db=db;self.reader_token=reader_token;self.operator_token=operator_token
        super().__init__(address,Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(5)

    def log_message(self,*args): pass  # request URLs/headers are never secret logs

    def role(self):
        value=self.headers.get('Authorization','')
        if not value.startswith('Bearer '): return None
        token=value[7:]
        if self.server.operator_token and hmac.compare_digest(token,self.server.operator_token): return 'operator'
        if hmac.compare_digest(token,self.server.reader_token): return 'reader'
        return None

    def reply(self,code,body):
        data=json.dumps(body).encode();self.send_response(code)
        self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)

    def do_GET(self):
        if self.path=='/health': return self.reply(200,{'alive':True})
        if not self.role(): return self.reply(401,{'error':'authentication required'})
        if self.path=='/status': return self.reply(200,status(self.server.db))
        if self.path=='/ready':
            view=status(self.server.db)
            ready=not view['stale'] and not view['halts'] and bool(view['instances']) and all(i['status']=='READY' and not i['halt'] for i in view['instances'])
            return self.reply(200 if ready else 503,{'ready':ready})
        if self.path.startswith('/evidence/'):
            hash=self.path.removeprefix('/evidence/')
            if len(hash)!=64 or any(c not in '0123456789abcdef' for c in hash): return self.reply(400,{'error':'invalid evidence hash'})
            with self.server.db.mutex: row=self.server.db.connection.execute('SELECT body FROM snapshots WHERE hash=?',(hash,)).fetchone()
            return self.reply(200,json.loads(row['body'])) if row else self.reply(404,{'error':'evidence not found'})
        return self.reply(404,{'error':'not found'})


@contextmanager
def serving(db,settings):
    if not settings:
        yield None;return
    token=lambda key:Path(settings[key]).read_text().strip()
    server=Server((settings.get('host','0.0.0.0'),settings.get('port',9010)),db,token('reader_token'),token('operator_token') if settings.get('operator_token') else None)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield server
    finally: server.shutdown();server.server_close();thread.join(5)
