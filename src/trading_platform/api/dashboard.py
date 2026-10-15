"""Loopback-published UI proxy. No DB mount and no browser-embedded credentials."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path in ('/','/app.js'):
            name='dashboard.html' if self.path=='/' else 'dashboard.js'
            data=Path(__file__).with_name(name).read_bytes();code=200
            content='text/html; charset=utf-8' if self.path=='/' else 'text/javascript'
        elif self.path.startswith('/api/'):
            try:
                req=Request(self.server.upstream+self.path[4:],headers={'Authorization':self.headers.get('Authorization','')})
                with urlopen(req,timeout=5) as response: data=response.read(2*1024*1024);code=response.status
            except HTTPError as exc: data=exc.read();code=exc.code
            except (URLError,TimeoutError): data=b'{"error":"core unavailable"}';code=503
            content='application/json'
        else: data=b'Not found';code=404;content='text/plain'
        self.send_response(code);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers();self.wfile.write(data)


def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream',default='http://core:9010');p.add_argument('--port',type=int,default=8080)
    args=p.parse_args();server=ThreadingHTTPServer(('0.0.0.0',args.port),Handler);server.upstream=args.upstream;server.serve_forever()

if __name__=='__main__': main()
