"""Quiesced, checksummed paper backups and isolated restore with an entry halt."""
import argparse,fcntl,hashlib,json,os,shutil,sqlite3,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from .database import Database
from trading_platform.contracts.values import canonical


def checksum(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def backup(database,broker,destination):
    database,broker,destination=Path(database),Path(broker),Path(destination)
    if not database.is_file() or not broker.is_file(): raise ValueError('complete paper state required')
    destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    started=time.monotonic()
    try:
        # Both writer locks must be held: never copy a running paper simulator.
        with open(str(broker)+'.lock','a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with Database(database) as db:
                with db.mutex: db.backup(destination/'core.sqlite')
                schema=db.connection.execute('PRAGMA user_version').fetchone()[0]
                cursor=db.connection.execute('SELECT max(seq) FROM events').fetchone()[0] or 0
            shutil.copyfile(broker,destination/'broker.json')
        manifest={'format':1,'mode':'paper','schema':schema,'created_at':datetime.now(timezone.utc).isoformat(),'event_cursor':cursor,
            'files':{name:checksum(destination/name) for name in ('core.sqlite','broker.json')},'quiesced':True,'rpo_events':0,'backup_seconds':time.monotonic()-started}
        (destination/'manifest.json').write_text(canonical(manifest))
        for path in destination.iterdir():
            path.chmod(0o600)
            with path.open('rb') as file: os.fsync(file.fileno())
        return manifest
    except BaseException:
        # Keep a failed artifact distinguishable; never present it as a valid backup.
        (destination/'INCOMPLETE').touch();raise


def verify(archive):
    archive=Path(archive)
    if (archive/'INCOMPLETE').exists(): raise ValueError('incomplete backup')
    manifest=json.loads((archive/'manifest.json').read_text())
    if manifest.get('format')!=1 or manifest.get('mode')!='paper' or manifest.get('schema')!=1 or not manifest.get('quiesced'): raise ValueError('unsupported backup')
    if set(manifest.get('files',{}))!={'core.sqlite','broker.json'}: raise ValueError('backup file set')
    for name,hash in manifest['files'].items():
        if checksum(archive/name)!=hash: raise ValueError('backup checksum mismatch')
    with sqlite3.connect('file:'+str((archive/'core.sqlite').resolve())+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('database integrity')
        if db.execute('PRAGMA user_version').fetchone()[0]!=manifest['schema']: raise ValueError('schema mismatch')
    json.loads((archive/'broker.json').read_text())
    return manifest


def restore(archive,destination):
    manifest=verify(archive);destination=Path(destination)
    destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    shutil.copyfile(Path(archive)/'core.sqlite',destination/'core.db')
    shutil.copyfile(Path(archive)/'broker.json',destination/'paper.json')
    for path in destination.iterdir(): path.chmod(0o600)
    with Database(destination/'core.db') as db:
        with db.transaction() as c:
            c.execute('INSERT OR REPLACE INTO halts VALUES (?,?)',('restore','RESTORED_REQUIRES_ISOLATED_RECONCILIATION'))
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('operations:control',canonical({'paused':True,'by':'restore'})))
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('restore:manifest',canonical(manifest)))
    return manifest


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('backup');b.add_argument('--database',required=True);b.add_argument('--broker',required=True);b.add_argument('--destination',required=True)
    r=sub.add_parser('restore');r.add_argument('--archive',required=True);r.add_argument('--destination',required=True)
    v=sub.add_parser('verify');v.add_argument('--archive',required=True)
    a=p.parse_args()
    result=backup(a.database,a.broker,a.destination) if a.command=='backup' else restore(a.archive,a.destination) if a.command=='restore' else verify(a.archive)
    print(json.dumps(result))

if __name__=='__main__': main()
