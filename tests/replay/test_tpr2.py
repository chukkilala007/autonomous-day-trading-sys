import json
from datetime import timedelta
from decimal import Decimal as D

from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Bar, Event
from trading_platform.contracts.values import utc
from trading_platform.strategies.tpr2.adapter import TPR2, limit_execution_check
from trading_platform.strategies.tpr2.baseline import Engine, VERSION
from tests.replay.test_tpr_adapter import executable_snapshot
from tests.replay.test_tpr_baseline import bar, fixture


def engine(m5):
    return Engine('XAUUSD', m5, tolerance='.1', price_step='.01')


def instance(mode='paper'):
    account = dict(alias='paper', environment='paper')
    if mode == 'shadow': account = dict(alias='demo-shadow', environment='demo', broker_account='12')
    return Instance.model_validate_json(json.dumps(dict(instance_id='tpr2', strategy='tpr2@1',
        package_digest='test', mode=mode, universe=['XAUUSD'], account=account, allocation='0.005')))


def evidence(cutoff):
    return dict(price_basis='bid', tick_size='0.01', actual_session_open=True,
        session_source_time=cutoff.isoformat(),
        provenance={k: 'synthetic-test-fixture' for k in ('price_basis', 'tick_size', 'actual_session_open')})


def test_preregistered_limit_retest_geometry_and_version_are_distinct():
    m5, m1 = fixture(); result = engine(m5).run(m1); trigger = result['events'][-1]
    assert result['version'] == VERSION == 'TPR-2'
    assert trigger['candidate_id'].startswith('TPR-2/')
    assert trigger['plan']['entry'] == '108.5'
    assert trigger['plan']['stop'] == '108.28'
    assert trigger['plan']['entry_semantics'] == 'post_rejection_limit_retest'
    assert trigger['entry_expires'] == '2024-01-01T01:33:00Z'
    assert result['parameters']['pending_bars'] == 2


def test_limit_touch_is_after_trigger_and_uses_retest_direction():
    m5, m1 = fixture()
    untouched = bar(m1[-1].t+60, 108.7, 108.8, 108.6, 108.7)
    touched = bar(m1[-1].t+120, 108.7, 108.8, 108.49, 108.6)
    result = engine(m5).run(m1+[untouched, touched])
    assert result['events'][-1]['reason_codes'] == ['ENTRY_TOUCHED']
    assert result['events'][-1]['setup_state'] == 'MISSED'


def test_limit_stop_same_bar_is_ambiguous_and_expiry_is_two_bars():
    m5, m1 = fixture()
    ambiguous = bar(m1[-1].t+60, 108.7, 108.8, 108.1, 108.4)
    assert engine(m5).run(m1+[ambiguous])['events'][-1]['reason_codes'] == ['AMBIGUOUS_TOUCH']
    tail = [bar(m1[-1].t+i*60, 108.7, 108.8, 108.6, 108.7) for i in (1, 2)]
    assert engine(m5).run(m1+tail)['events'][-1]['reason_codes'] == ['ENTRY_EXPIRED']


def test_gap_blocks_retest_and_appended_future_does_not_change_prefix():
    m5, m1 = fixture(); partial = engine(m5).run(m1)['events']
    gap = bar(m1[-1].t+120, 108.7, 108.8, 108.6, 108.7)
    assert engine(m5).run(m1+[gap])['events'][-1]['reason_codes'] == ['DATA_GAP']
    future_m5 = m5+[bar(m5[-1].t+300, 110, 113, 109, 112)]
    tail = [bar(m1[-1].t+i*60, 108.7, 108.8, 108.6, 108.7) for i in (1, 2)]
    full = engine(future_m5).run(m1+tail)['events']
    cutoff = partial[-1]['decision_time']
    assert partial == [event for event in full if event['decision_time'] <= cutoff]


def test_short_limit_retest_mirrors_long():
    m5, m1 = fixture(True); trigger = engine(m5).run(m1)['events'][-1]
    assert trigger['direction'] == 'short'
    assert D(trigger['plan']['entry']) == D('91.5')
    touch = bar(m1[-1].t+60, 91.3, 91.51, 91.2, 91.4)
    assert engine(m5).run(m1+[touch])['events'][-1]['reason_codes'] == ['ENTRY_TOUCHED']


def test_adapter_emits_protected_limit_in_paper_and_shadow_only_with_evidence():
    snapshot = executable_snapshot(); plugin = TPR2()
    payload = json.dumps({'execution_evidence': evidence(snapshot.cutoff)})
    event = Event(event_id='e', kind='bar', instrument='XAUUSD', source_time=snapshot.cutoff,
                  available_at=snapshot.cutoff, payload=payload)
    for mode in ('paper', 'shadow'):
        configured = instance(mode); out = plugin.evaluate(configured, event, snapshot, (), plugin.initialize(configured))
        decision = out.decisions[0]
        assert decision.outcome == 'ENTRY', decision.reasons
        assert decision.proposal.order_type == 'limit'
        assert decision.proposal.profile == 'protected'
        plugin.validate_proposal(decision.proposal, snapshot)


def test_adapter_without_execution_evidence_only_watches_and_live_is_rejected():
    snapshot = executable_snapshot(); plugin = TPR2(); configured = instance()
    event = Event(event_id='e', kind='bar', instrument='XAUUSD', source_time=snapshot.cutoff,
                  available_at=snapshot.cutoff)
    decision = plugin.evaluate(configured, event, snapshot, (), plugin.initialize(configured)).decisions[0]
    assert decision.outcome == 'WATCH' and 'EXECUTION_UNVERIFIED' in decision.reasons
    live = configured.model_copy(update={'mode': 'live', 'account': configured.account.model_copy(
        update={'environment': 'live', 'broker_account': '12'})})
    try:
        plugin.initialize(live)
        assert False, 'live TPR-2 must fail closed'
    except ValueError as exc:
        assert 'not live-qualified' in str(exc)


def test_limit_quote_side_blocks_already_touched_retest():
    base = 1704067200
    plan = {'entry': '100', 'stop': '99', 'tp1': '102', 'risk': '1', 'reward': '2',
            'gross_rr': '2', 'geometry_basis': 'executable'}
    metadata = {'tick_size': '.01', 'actual_session_open': True, 'price_basis': 'bid',
        'session_source_time': '2024-01-01T00:00:00Z', 'availability_asof': '2024-01-01T00:00:00Z',
        'context_screen_complete': True,
        'provenance': {k: 'test' for k in ('tick_size', 'actual_session_open', 'price_basis')}}
    pending = limit_execution_check(plan, {'bid': '100.01', 'ask': '100.02',
        'source_time': '2024-01-01T00:00:00Z'}, metadata, base, direction='long')
    touched = limit_execution_check(plan, {'bid': '99.98', 'ask': '99.99',
        'source_time': '2024-01-01T00:00:00Z'}, metadata, base, direction='long')
    assert pending['entry_ready']
    assert not touched['entry_ready'] and 'ENTRY_TOUCHED' in touched['reasons']


def test_package_source_has_no_tpr1_runtime_import():
    from pathlib import Path
    source = '\n'.join(path.read_text() for path in Path('src/trading_platform/strategies/tpr2').glob('*.py'))
    assert 'strategies.tpr1' not in source
