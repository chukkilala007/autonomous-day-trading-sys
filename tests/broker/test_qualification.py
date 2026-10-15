from trading_platform.gateways.ctrader.qualification import report,ACTUAL,FAULTS


def test_passing_transport_tests_cannot_qualify_demo():
    evidence=[dict(scenario=s,account='12',result='pass',artifact_hash='synthetic-test',observed_at='2026-01-01T00:00:00Z',source='deterministic_transport',unexplained_exposure=False,duplicate_submissions=0) for s in ACTUAL|FAULTS]
    result=report(12,evidence)
    assert not result['qualified'] and set(result['missing'])==ACTUAL
    assert not result['live_enabled']
    assert not report(12,[])['qualified']
    assert not report(13,evidence)['qualified']
