import runpy
from datetime import timedelta
import pytest
from trading_platform.runtime.controls import Controls
from trading_platform.observability.alerts import Alerts
from trading_platform.persistence.database import Database
from trading_platform.runtime.paper import PaperRuntime
from trading_platform.simulation.broker import PaperBroker
from trading_platform.simulation.replay import load_registry


def test_pause_resume_and_flatten_have_distinct_idempotent_effects(tmp_path):
    instances,rows=runpy.run_path('tests/execution/test_runtime.py')['inputs']()
    with Database(tmp_path/'db') as db:
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker());runtime.process(*rows[0])
        controls=runtime.controls;at=rows[0][1].cutoff
        controls.submit('pause','pause',at,role='operator');controls.pump(runtime,at,rows[0][1])
        assert len(runtime.status()['active_risk'])==2 and controls.state()['paused']
        with pytest.raises(ValueError): controls.submit('other','pause',at,role='reader')
        with pytest.raises(ValueError): controls.submit('pause','resume',at,role='operator')
        controls.submit('resume','resume',at,role='operator');controls.pump(runtime,at,rows[0][1])
        assert not controls.state()['paused']
        controls.submit('flatten','flatten',at,role='operator')
        controls.pump(runtime,at,rows[0][1]);controls.pump(runtime,at,rows[0][1])
        status=runtime.status()
        assert not status['positions'] and not status['active_risk']
        count=len(status['orders'])
        controls.submit('flatten','flatten',at,role='operator');controls.pump(runtime,at,rows[0][1])
        assert len(runtime.status()['orders'])==count
        controls.submit('blocked-resume','resume',at,role='operator');controls.pump(runtime,at,rows[0][1])
        assert controls.state()['paused']


def test_alert_transitions_persist_and_deduplicate(tmp_path):
    with Database(tmp_path/'db') as db:
        alerts=Alerts(db)
        assert alerts.transition('feed',False,'DATA_STALE','now') is None
        assert alerts.transition('feed',True,'DATA_STALE','now')['kind']=='OPEN'
        assert alerts.transition('feed',True,'DATA_STALE','later') is None
    with Database(tmp_path/'db') as db:
        alerts=Alerts(db)
        assert alerts.transition('feed',True,'DATA_STALE','again') is None
        assert alerts.transition('feed',False,'DATA_STALE','fixed')['kind']=='RECOVERED'
        assert db.connection.execute("SELECT count(*) FROM checkpoints WHERE id LIKE 'alert:%'").fetchone()[0]==2
