"""Build/verify a reproducible paper release handoff from committed Git blobs.

Never starts Docker, publishes images, includes local secrets, or enables orders.
Digest references are supplied release inputs, not proof of registry publication.
"""
import argparse,hashlib,json,re,subprocess
from pathlib import Path,PurePosixPath
from release_manifest import manifest

ROOT_FILES={'compose.yaml','Dockerfile','pyproject.toml','README.md','LICENSE'}
ROOTS={'config','requirements','src','scripts','deploy','docs'}
FIXTURES={'tests/fixtures/paper.json'}
TOKENS={'tests/smoke/'+n+'-token.txt' for n in ('tpr','timer','broker','reader','operator')}


def allowed(name):
    path=PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts and
            (name in ROOT_FILES or name in FIXTURES or name in TOKENS or path.parts[0] in ROOTS))


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args])


def build(root,destination,image):
    root=Path(root);destination=Path(destination)
    sha=git(root,'rev-parse','HEAD').decode().strip()
    if git(root,'status','--porcelain'): raise ValueError('commit changes before release packaging')
    override=manifest(image)
    entries={}
    for raw in git(root,'ls-tree','-rz','--full-tree','HEAD').split(b'\0'):
        if not raw: continue
        meta,name=raw.split(b'\t',1);mode,kind,blob=meta.decode().split();name=name.decode()
        if not allowed(name): continue
        if mode not in ('100644','100755') or kind!='blob': raise ValueError('release contains nonregular file')
        entries[name]=git(root,'cat-file','blob',blob)
    if 'compose.yaml' not in entries or not TOKENS<=entries.keys(): raise ValueError('incomplete paper release inputs')
    entries['release.json']=(json.dumps(override,sort_keys=True,indent=2)+'\n').encode()
    metadata=dict(format=1,mode='paper',broker_orders_enabled=False,source_commit=sha,image=image,
                  registry_verified=False,files={n:hashlib.sha256(b).hexdigest() for n,b in sorted(entries.items())})
    destination.mkdir(mode=0o700,parents=False,exist_ok=False)
    (destination/'INCOMPLETE').write_text('Do not deploy until packaging and verification succeed.\n')
    for name,body in entries.items():
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    (destination/'bundle.json').write_text(json.dumps(metadata,sort_keys=True,indent=2)+'\n')
    (destination/'INCOMPLETE').unlink()
    verify(destination)
    return metadata


def verify(root):
    root=Path(root)
    if root.is_symlink() or (root/'INCOMPLETE').exists(): raise ValueError('incomplete or linked bundle')
    metadata=json.loads((root/'bundle.json').read_text())
    if metadata.get('format')!=1 or metadata.get('mode')!='paper' or metadata.get('broker_orders_enabled') is not False:
        raise ValueError('unsupported release mode')
    if not re.fullmatch('[0-9a-f]{40}',metadata['source_commit']): raise ValueError('invalid source commit')
    expected=manifest(metadata['image'])
    for name,checksum in metadata['files'].items():
        if not (allowed(name) or name=='release.json'): raise ValueError('unexpected release path')
        path=root/name
        if any(p.is_symlink() for p in [path,*path.parents]) or not path.is_file(): raise ValueError('nonregular release file')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=checksum: raise ValueError('release checksum mismatch')
    files={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    if files!=set(metadata['files'])|{'bundle.json'}: raise ValueError('unmanifested release file')
    if not {'compose.yaml','release.json',*TOKENS}<=set(metadata['files']): raise ValueError('missing release inputs')
    if json.loads((root/'release.json').read_text())!=expected: raise ValueError('release override mismatch')
    return metadata


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='op',required=True)
    b=sub.add_parser('build');b.add_argument('--repository',default='.');b.add_argument('--destination',required=True);b.add_argument('--image',required=True)
    v=sub.add_parser('verify');v.add_argument('directory');args=p.parse_args()
    result=build(args.repository,args.destination,args.image) if args.op=='build' else verify(args.directory)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__': main()
