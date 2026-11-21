"""Quiesced attended-ledger snapshots; restored ledgers remain entry-inhibited."""
from contextlib import closing
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

from trading_platform.contracts.values import canonical, digest
from .database import Database

HALT = 'restore:attended'


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_scope(connection, account):
    rows = list(connection.execute('SELECT id,body FROM checkpoints'))
    scoped = ('attended-attempt:', 'attended-monitor:', 'active-test-cycle:',
              'completed-test:', 'consumed-test:', 'consumed-approval:', 'gateway-fence:')
    found = False
    for key, body in rows:
        for prefix in scoped:
            if key.startswith(prefix):
                if key[len(prefix):].split(':')[0] != account:
                    raise ValueError('foreign ledger account')
                found = True
        if key.startswith('gateway-send:'):
            if str(json.loads(body)['fields']['ctidTraderAccountId']) != account:
                raise ValueError('foreign send account')
    if not found:
        raise ValueError('account-scoped attended ledger required')


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def backup(database, destination, account):
    database, destination = Path(database), Path(destination)
    account = str(account)
    if not database.is_file() or database.is_symlink():
        raise ValueError('regular ledger required')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        with Database(database) as db:
            check_scope(db.connection, account)
            db.backup(destination / 'ledger.sqlite')
        manifest = dict(format=1, mode='attended-demo', account_id=account,
                        schema=1, quiesced=True, ledger_sha256=checksum(destination / 'ledger.sqlite'))
        (destination / 'manifest.json').write_text(canonical(manifest))
        for path in destination.iterdir():
            path.chmod(0o600)
            with path.open('rb') as stream:
                os.fsync(stream.fileno())
        sync_directory(destination)
        return dict(manifest=manifest, manifest_hash=digest(manifest))
    except BaseException:
        (destination / 'INCOMPLETE').touch(mode=0o600)
        raise


def verify(archive, account, approved_manifest_hash):
    archive = Path(archive)
    if archive.is_symlink() or {p.name for p in archive.iterdir()} != {'ledger.sqlite', 'manifest.json'}:
        raise ValueError('incomplete or unexpected archive files')
    if any(p.is_symlink() or not p.is_file() for p in archive.iterdir()):
        raise ValueError('regular archive files required')
    manifest = json.loads((archive / 'manifest.json').read_text())
    if (digest(manifest) != approved_manifest_hash or manifest.get('format') != 1
            or manifest.get('mode') != 'attended-demo' or manifest.get('schema') != 1
            or manifest.get('quiesced') is not True or manifest.get('account_id') != str(account)):
        raise ValueError('unapproved account-scoped archive')
    path = archive / 'ledger.sqlite'
    if checksum(path) != manifest['ledger_sha256']:
        raise ValueError('archive checksum mismatch')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ValueError('invalid ledger schema/integrity')
        check_scope(db, str(account))
    return manifest


def restore(archive, destination, account, approved_manifest_hash):
    manifest = verify(archive, account, approved_manifest_hash)
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    marker = destination / 'INCOMPLETE'
    marker.touch(mode=0o600)
    staging = destination / 'ledger.restoring'
    shutil.copyfile(Path(archive) / 'ledger.sqlite', staging)
    staging.chmod(0o600)
    if checksum(staging) != manifest['ledger_sha256']:
        raise ValueError('archive changed while restoring')
    with Database(staging) as db:
        with db.transaction() as c:
            c.execute('INSERT OR REPLACE INTO halts VALUES (?,?)',
                      (HALT, 'RESTORED_ATTENDED_LEDGER_REQUIRES_REVIEW'))
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',
                      (HALT, canonical(dict(account_id=str(account), manifest_hash=approved_manifest_hash,
                                            entries_disabled=True))))
            key = 'gateway-fence:' + str(account)
            row = c.execute('SELECT body FROM checkpoints WHERE id=?', (key,)).fetchone()
            epoch = json.loads(row[0])['epoch'] if row else 0
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',
                      (key, canonical(dict(core='restore-inhibited', epoch=epoch+1))))
    with staging.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(staging, destination / 'ledger.sqlite')
    marker.unlink()
    sync_directory(destination)
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['backup', 'verify', 'restore'])
    p.add_argument('--account', required=True)
    p.add_argument('--database')
    p.add_argument('--archive')
    p.add_argument('--destination')
    p.add_argument('--approved-manifest-hash')
    a = p.parse_args()
    if a.action == 'backup':
        if not a.database or not a.destination: p.error('backup requires database and destination')
        value = backup(a.database, a.destination, a.account)
    else:
        if not a.archive or not a.approved_manifest_hash: p.error('archive and approved manifest hash required')
        if a.action == 'restore':
            if not a.destination: p.error('restore destination required')
            value = restore(a.archive, a.destination, a.account, a.approved_manifest_hash)
        else:
            value = verify(a.archive, a.account, a.approved_manifest_hash)
    print(canonical(value))


if __name__ == '__main__':
    main()
