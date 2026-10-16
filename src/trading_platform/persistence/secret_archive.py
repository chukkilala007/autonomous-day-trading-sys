"""Offline authenticated secret archives; keys stay separate from ciphertext.

Run in the gateway/tools image (cryptography is pinned in gateway.lock).
No network transfer or broker activation is performed by this module.
"""
import argparse,base64,json,os,re,stat
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC=b'TRADING-SECRETS-1\n'
MAX_FILE=1024*1024
MAX_ARCHIVE=16*MAX_FILE


def private_read(path,limit=MAX_FILE):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_mode & 0o077: raise ValueError('private regular file required')
        if before.st_size>limit: raise ValueError('file exceeds size limit')
        with os.fdopen(os.dup(fd),'rb') as stream:data=stream.read(limit+1)
        after=os.fstat(fd)
        if len(data)>limit or (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns): raise ValueError('source changed during backup')
        return data
    finally:os.close(fd)


def exclusive_write(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    directory=os.open(Path(path).parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)


def read_key(path):
    key=private_read(path)
    if len(key)!=32:raise ValueError('32-byte archive key required')
    return key


def backup(key_path,sources,destination):
    key=read_key(key_path)
    if not 1<=len(sources)<=8:raise ValueError('one to eight named secret files required')
    payload={}
    for name,path in sources.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(json|key|txt)',name):raise ValueError('invalid archive name')
        if Path(path).resolve()==Path(key_path).resolve():raise ValueError('archive key cannot be included')
        payload[name]=base64.b64encode(private_read(path)).decode('ascii')
    nonce=os.urandom(12)
    ciphertext=AESGCM(key).encrypt(nonce,json.dumps(payload,sort_keys=True).encode(),MAGIC)
    exclusive_write(destination,MAGIC+nonce+ciphertext)
    return {'files':len(payload),'encrypted':True}


def restore(key_path,archive,destination):
    data=private_read(archive,MAX_ARCHIVE)
    if not data.startswith(MAGIC):raise ValueError('unsupported secret archive')
    nonce=data[len(MAGIC):len(MAGIC)+12]
    # Authenticate the complete payload before creating any destination files.
    from cryptography.exceptions import InvalidTag
    try:payload=json.loads(AESGCM(read_key(key_path)).decrypt(nonce,data[len(MAGIC)+12:],MAGIC))
    except (InvalidTag,ValueError,TypeError) as exc:raise ValueError('archive authentication failed') from None
    if not isinstance(payload,dict) or not 1<=len(payload)<=8:raise ValueError('invalid archive manifest')
    decoded={}
    for name,value in payload.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(json|key|txt)',name):raise ValueError('unsafe archive path')
        raw=base64.b64decode(value,validate=True)
        if len(raw)>MAX_FILE:raise ValueError('secret exceeds size limit')
        decoded[name]=raw
    root=Path(destination);root.mkdir(mode=0o700,exist_ok=False)
    marker=root/'INCOMPLETE';exclusive_write(marker,b'Restore incomplete; do not activate credentials.\n')
    for name,raw in decoded.items():exclusive_write(root/name,raw)
    marker.unlink()
    directory=os.open(root,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return {'files':len(decoded),'restored':True,'broker_activation':False}


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    key=sub.add_parser('keygen');key.add_argument('--output',required=True)
    save=sub.add_parser('backup');save.add_argument('--key',required=True);save.add_argument('--source',action='append',required=True,help='NAME=PATH');save.add_argument('--output',required=True)
    load=sub.add_parser('restore');load.add_argument('--key',required=True);load.add_argument('--archive',required=True);load.add_argument('--destination',required=True)
    args=parser.parse_args()
    if args.action=='keygen':exclusive_write(args.output,os.urandom(32));result={'key_created':True}
    elif args.action=='backup':
        pairs=[s.split('=',1) for s in args.source]
        if any(len(p)!=2 for p in pairs) or len({p[0] for p in pairs})!=len(pairs):raise ValueError('unique NAME=PATH sources required')
        result=backup(args.key,dict(pairs),args.output)
    else:result=restore(args.key,args.archive,args.destination)
    print(json.dumps(result))

if __name__=='__main__':main()
