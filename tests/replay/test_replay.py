import json,runpy
from pathlib import Path
import pytest
from trading_platform.simulation.replay import load_registry,replay,records
from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Event,Quote
from trading_platform.contracts.snapshots import Snapshot


def test_both_packages_replay_deterministically():
    helper=runpy.run_path('tests/replay/test_tpr_adapter.py')
    s=helper['executable_snapshot']()
    q=Quote(instrument='TEST',bid='100',ask='100.01',source_time=s.cutoff,received_at=s.cutoff)
    s=s.model_copy(update={'quotes':s.quotes+(q,)})
    e=Event(event_id='1',kind='bar',instrument='XAUUSD',source_time=s.cutoff,available_at=s.cutoff)
    for name in ('tpr1','timer_fixture'):
        i=Instance.model_validate_json(Path(f'config/instances/{name}.json').read_text())
        a=replay(i,load_registry('config/registry.json'),[(e,s)])
        b=replay(i,load_registry('config/registry.json'),[(e,s)])
        assert a==b and a['pnl'] is None
        assert a['decisions']


def test_input_conflicting_revision_rejected(tmp_path):
    t='2024-01-01T00:00:00Z'
    row=dict(event=dict(event_id='e',kind='timer',instrument='X',source_time=t,available_at=t),snapshot=dict(cutoff=t))
    p=tmp_path/'input.json';p.write_text(json.dumps([row,row]))
    assert len(records(p))==1
    other=dict(row,event=row['event']|{'payload':'{"different":1}'})
    p.write_text(json.dumps([row,other]))
    with pytest.raises(ValueError): records(p)
