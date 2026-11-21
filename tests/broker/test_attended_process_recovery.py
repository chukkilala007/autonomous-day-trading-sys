"""Kill an OS process, reopen its actual SQLite WAL, and resume in a new process."""
import json
from pathlib import Path
import signal
import subprocess
import sys

import pytest


@pytest.mark.parametrize('scenario', ['pending', 'cancel', 'close'])
def test_attended_process_kill_preserves_attempt_and_cleanup(tmp_path, scenario):
    worker = Path(__file__).with_name('attended_crash_worker.py')
    crashed = subprocess.run([sys.executable, str(worker), str(tmp_path), 'crash', scenario],
                             capture_output=True, text=True, timeout=20)
    assert crashed.returncode == -signal.SIGKILL, crashed.stdout + crashed.stderr
    before = [json.loads(line)['name'] for line in (tmp_path / 'wire.jsonl').read_text().splitlines()]
    action = 'ProtoOAClosePositionReq' if scenario == 'close' else 'ProtoOACancelOrderReq'
    assert before == (['ProtoOANewOrderReq'] if scenario == 'pending'
                      else ['ProtoOANewOrderReq', action])
    recovered = subprocess.run([sys.executable, str(worker), str(tmp_path), 'recover', scenario],
                               capture_output=True, text=True, timeout=20)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    writes = [json.loads(line)['name'] for line in (tmp_path / 'wire.jsonl').read_text().splitlines()]
    assert writes == ['ProtoOANewOrderReq', action]
    report = json.loads((tmp_path / 'recovery.json').read_text())
    assert report['status'] == ('CLEANUP_UNCONFIRMED' if scenario == 'close' else 'COMPLETE')
