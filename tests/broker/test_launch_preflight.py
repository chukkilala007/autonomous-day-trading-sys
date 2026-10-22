from datetime import timedelta
import pytest
from test_attended_binding import rig, T
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.launch_preflight import check, load_check


def run(x, **overrides):
    args = dict(account_id='12', approved_bundle_hash=digest(x.bundle), now=T)
    args.update(overrides)
    return check(x.bundle, x.entry, **args)


def test_valid_is_only_offline_input_check(rig):
    report = run(rig)
    assert report['status'] == 'INPUTS_VALIDATED_NOT_BROKER_READY'
    assert not report['orders_enabled'] and not report['broker_connected']
    assert rig.calls == []


@pytest.mark.parametrize('change,code', [
    ({'account_id':'other'}, 'UNSUPPORTED_ACCOUNT_CONTRACT'),
    ({'approved_bundle_hash':'b'*64}, 'REVIEW_PIN_MISMATCH'),
    ({'now':T+timedelta(days=2)}, 'POLICY_NOT_CURRENT'),
    ({'now':T+timedelta(seconds=11)}, 'PROPOSAL_NOT_CURRENT'),
    ({'now':T-timedelta(seconds=1)}, 'PROPOSAL_NOT_CURRENT'),
])
def test_rejects_invalid_binding_or_time(rig, change, code):
    assert code in run(rig, **change)['blockers']


def test_rejects_off_grid_and_unsupported_proposal(rig):
    rig.entry = rig.entry.model_copy(update={'entry':rig.entry.entry + __import__('decimal').Decimal('0.000001')})
    assert set(run(rig)['blockers']) == {'PRICE_GRID_MISMATCH','UNSUPPORTED_PROPOSAL'}


def test_files_fail_closed_without_echoing_sensitive_input(tmp_path):
    args = dict(account_id='12', approved_bundle_hash='a'*64, now=T)
    bundle = tmp_path/'bundle'
    assert load_check(bundle,tmp_path/'entry',**args)['blockers'] == ['REVIEW_REQUIRED']
    bundle.write_text('{"secret":"do-not-print"}')
    report = load_check(bundle,tmp_path/'entry',**args)
    assert report['blockers'] == ['INVALID_REVIEW_FILE']
    assert 'do-not-print' not in str(report)


def test_valid_review_missing_proposal(rig, tmp_path):
    bundle = tmp_path/'bundle'; bundle.write_text(rig.bundle.model_dump_json())
    assert load_check(bundle,tmp_path/'missing',account_id='12',approved_bundle_hash=digest(rig.bundle),now=T)['blockers'] == ['INVALID_PROPOSAL_FILE']
