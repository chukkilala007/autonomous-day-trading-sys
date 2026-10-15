"""Authenticated bounded framing for private Docker networks. No pickle."""
import hmac,json,socket,struct,secrets
from trading_platform.contracts.values import canonical
MAX_BYTES=1024*1024


def read_exact(sock,n):
    chunks=bytearray()
    while len(chunks)<n:
        part=sock.recv(n-len(chunks))
        if not part: raise ValueError('truncated frame')
        chunks.extend(part)
    return bytes(chunks)


def receive(sock):
    size=struct.unpack('!I',read_exact(sock,4))[0]
    if size<2 or size>MAX_BYTES: raise ValueError('frame size')
    msg=json.loads(read_exact(sock,size))
    if not isinstance(msg,dict): raise ValueError('message object required')
    canonical(msg)
    return msg


def send(sock,msg):
    body=canonical(msg).encode()
    if len(body)>MAX_BYTES: raise ValueError('frame size')
    sock.sendall(struct.pack('!I',len(body))+body)


def authorize(msg,token,instance):
    if msg.get('version')!=1 or msg.get('role')!='core' or msg.get('instance')!=instance:
        raise ValueError('invalid handshake')
    if not isinstance(msg.get('token'),str) or not hmac.compare_digest(msg['token'],token):
        raise ValueError('unauthorized')
    if not isinstance(msg.get('request_id'),str): raise ValueError('request ID required')


def request(host,port,token,instance,body,timeout=5):
    request_id=secrets.token_hex(16)
    with socket.create_connection((host,port),timeout=timeout) as sock:
        sock.settimeout(timeout)
        send(sock,dict(version=1,role='core',token=token,instance=instance,request_id=request_id,body=body))
        response=receive(sock)
        if response.get('request_id')!=request_id: raise ValueError('stale response')
        if 'error' in response: raise ValueError(response['error'])
        return response['body']
