import socket,struct,threading
import pytest
from trading_platform.runtime.transport import request,receive,MAX_BYTES
from trading_platform.runtime.worker import Server
TOKEN='a'*32

def test_worker_auth_and_identity():
    with Server(('127.0.0.1',0),TOKEN,'worker') as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        host,port=server.server_address
        assert request(host,port,TOKEN,'worker',{'op':'ping'})['healthy']
        with pytest.raises(ValueError): request(host,port,'b'*32,'worker',{'op':'ping'})
        with pytest.raises(ValueError): request(host,port,TOKEN,'other',{'op':'ping'})
        server.shutdown();thread.join()

def test_bounded_and_timeout():
    a,b=socket.socketpair()
    try:
        a.sendall(struct.pack('!I',MAX_BYTES+1))
        with pytest.raises(ValueError): receive(b)
        b.settimeout(.02)
        with pytest.raises(TimeoutError): receive(b)
    finally: a.close();b.close()
