from datetime import datetime, timedelta, timezone
from trading_platform.gateways.ctrader.metadata import CapabilityReport, Evidence
from trading_platform.gateways.ctrader.shadow_evidence import execution_evidence

T=datetime(2026,11,24,tzinfo=timezone.utc)


def report(**changes):
    values={'tick_grid':'.01','candle_basis':'bid','session_state':'OPEN'};values.update(changes)
    rows=tuple(Evidence(field=field,value=value,source='actual-demo-probe',observed_at=T-timedelta(seconds=2),
        valid_until=T+timedelta(minutes=1),classification='demo_observed') for field,value in values.items())
    return CapabilityReport(account_id='12',symbol='XAUUSD',evidence=rows)


def test_only_complete_fresh_execution_evidence_is_exported():
    result=execution_evidence({'XAUUSD':report()},T)
    assert result=={'XAUUSD':{'tick_size':'0.01','actual_session_open':True,
        'session_source_time':'2026-11-23T23:59:58+00:00','price_basis':'bid',
        'provenance':{'tick_size':'actual-demo-probe','actual_session_open':'actual-demo-probe',
                      'price_basis':'actual-demo-probe'}}}


def test_stale_closed_invalid_or_incomplete_evidence_is_omitted():
    assert not execution_evidence({'XAUUSD':report()},T+timedelta(seconds=31))
    assert not execution_evidence({'XAUUSD':report(session_state='CLOSED')},T)
    assert not execution_evidence({'XAUUSD':report(tick_grid='unknown')},T)
    incomplete=report().model_copy(update={'evidence':report().evidence[:-1]})
    assert not execution_evidence({'XAUUSD':incomplete},T)
