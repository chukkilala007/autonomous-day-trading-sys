"""Restore actual attended checkpoints with synthetic broker state only."""
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys

import pytest

from trading_platform.contracts.values import canonical
from trading_platform.persistence.database import Database
from trading_platform.persistence.attended_archive import backup, restore, verify
from test_attended_adapter import adapter, rig, result


def seed(tmp_path, scenario='cancel'):
    root=tmp_path/'original';root.mkdir()
    worker=Path(__file__).with_name('attended_crash_worker.py')
    run=subprocess.run([sys.executable,str(worker),str(root),'crash',scenario],
                       capture_output=True,text=True,timeout=20)
    assert run.returncode==-signal.SIGKILL,run.stderr
    with Database(root/'state') as db:
        for key in ('completed-test:12:prior','consumed-test:12:prior','consumed-approval:12:prior'):
            db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',(key,canonical(dict(retained=True))))
        before=dict(db.connection.execute('SELECT id,body FROM checkpoints'))
    return root,worker,before


@pytest.mark.parametrize('scenario',['pending','cancel','close'])
def test_restore_retains_history_and_recovers_without_new_entries(tmp_path,scenario):
    root,worker,before=seed(tmp_path,scenario)
    archive=tmp_path/'archive'
    receipt=backup(root/'state',archive,'12')
    target=tmp_path/'restored'
    restore(archive,target,'12',receipt['manifest_hash'])
    assert (target/'ledger.sqlite').stat().st_mode & 0o777 == 0o600
    with Database(target/'ledger.sqlite') as db:
        after=dict(db.connection.execute('SELECT id,body FROM checkpoints'))
        for key,value in before.items():
            if key!='gateway-fence:12': assert after[key]==value
        assert json.loads(after['gateway-fence:12'])['epoch']>json.loads(before['gateway-fence:12'])['epoch']
        assert db.connection.execute("SELECT 1 FROM halts WHERE id='restore:attended'").fetchone()
    # Synthetic recovery worker expects this basename; source ledger untouched.
    (target/'ledger.sqlite').rename(target/'state')
    for name in ('broker.json','wire.jsonl'):
        shutil.copyfile(root/name,target/name)
    run=subprocess.run([sys.executable,str(worker),str(target),'recover',scenario],
                       capture_output=True,text=True,timeout=20)
    assert run.returncode==0,run.stderr
    writes=[json.loads(v)['name'] for v in (target/'wire.jsonl').read_text().splitlines()]
    assert writes==['ProtoOANewOrderReq','ProtoOAClosePositionReq' if scenario=='close' else 'ProtoOACancelOrderReq']
    with Database(target/'state') as db:
        assert db.connection.execute("SELECT 1 FROM halts WHERE id='restore:attended'").fetchone()
        assert db.connection.execute("SELECT count(*) FROM checkpoints WHERE id LIKE 'consumed-%'").fetchone()[0]==2
    with pytest.raises(FileExistsError):
        restore(archive,target,'12',receipt['manifest_hash'])


@pytest.mark.parametrize('marker',['halt','checkpoint'])
def test_restore_guard_blocks_adapter_and_both_transports(adapter,marker):
    from trading_platform.gateways.ctrader.first_test import FirstTestTransport
    x,a,calls=adapter;a.enabled=True
    if marker=='halt':
        x.db.connection.execute("INSERT INTO halts VALUES ('restore:attended','REVIEW')")
    else:
        x.feed.put('restore:attended',dict(entries_disabled=True))
    with pytest.raises(ValueError,match='restored attended'):
        result(a.submit(x.entry))
    for prepare in (a.gateway.prepare, lambda *args: FirstTestTransport.prepare(a.gateway,*args)):
        with pytest.raises(ValueError,match='restored attended'):
            prepare(None,None,None,None,None,None,None)
    assert calls==[]


@pytest.mark.parametrize('fault',['hash','account','tamper','incomplete','extra','symlink','schema'])
def test_invalid_archive_never_publishes_restore(tmp_path,fault):
    with Database(tmp_path/'source') as db:
        db.connection.execute("INSERT INTO checkpoints VALUES ('attended-attempt:12','{}')")
    receipt=backup(tmp_path/'source',tmp_path/'archive','12')
    pin=receipt['manifest_hash'];account='12';archive=tmp_path/'archive'
    if fault=='hash':pin='0'*64
    if fault=='account':account='13'
    if fault=='tamper':(archive/'ledger.sqlite').write_bytes(b'bad')
    if fault=='incomplete':(archive/'INCOMPLETE').touch()
    if fault=='extra':(archive/'extra').touch()
    if fault=='symlink':
        (archive/'ledger.sqlite').unlink();(archive/'ledger.sqlite').symlink_to(tmp_path/'source')
    if fault=='schema':
        from trading_platform.contracts.values import digest
        value=receipt['manifest'];value['schema']=999
        (archive/'manifest.json').write_text(canonical(value));pin=digest(value)
    with pytest.raises(ValueError):
        restore(archive,tmp_path/'restored',account,pin)
    assert not (tmp_path/'restored').exists()


def test_backup_requires_stopped_writer_and_correct_account(tmp_path):
    with Database(tmp_path/'source') as db:
        db.connection.execute("INSERT INTO checkpoints VALUES ('attended-attempt:12','{}')")
        with pytest.raises(ValueError,match='writer'):
            backup(tmp_path/'source',tmp_path/'busy','12')
    assert (tmp_path/'busy'/'INCOMPLETE').exists()
    with pytest.raises(ValueError,match='foreign'):
        backup(tmp_path/'source',tmp_path/'wrong','13')


def test_interrupted_restore_never_publishes_unhalted_ledger(tmp_path,monkeypatch):
    from trading_platform.persistence import attended_archive
    with Database(tmp_path/'source') as db:
        db.connection.execute("INSERT INTO checkpoints VALUES ('attended-attempt:12','{}')")
    receipt=backup(tmp_path/'source',tmp_path/'archive','12')
    def fail(*args):raise OSError('synthetic disk failure')
    monkeypatch.setattr(attended_archive.os,'replace',fail)
    with pytest.raises(OSError):
        restore(tmp_path/'archive',tmp_path/'restored','12',receipt['manifest_hash'])
    assert (tmp_path/'restored'/'INCOMPLETE').exists()
    assert not (tmp_path/'restored'/'ledger.sqlite').exists()
    assert verify(tmp_path/'archive','12',receipt['manifest_hash'])
