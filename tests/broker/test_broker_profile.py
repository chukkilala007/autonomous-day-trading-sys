"""All profiles below are synthetic; broker names do not establish qualification."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from pydantic import ValidationError
from trading_platform.gateways.ctrader.broker_profile import (
    AccountIdentity, SymbolMapping, CapabilityEvidence, BrokerProfile)

T = datetime(2026, 10, 23, tzinfo=timezone.utc)


def profile(broker='FxPro', tick='0.01', value='1', state='supported', classification='synthetic'):
    identity = AccountIdentity(broker=broker, account_id='test-account', environment='demo',
                               currency='USD', account_type='HEDGED')
    symbol = SymbolMapping(instrument='NAS100', native_symbol='#USNDAQ100', symbol_id=1107,
                           quote_currency='USD', tick=tick, minimum='0.01', maximum='500',
                           step='0.01', contract_value_per_unit=value)
    evidence = CapabilityEvidence(identity=identity, instrument='NAS100', symbol_id=1107,
                                  operation='BUY_LIMIT_GTD', state=state, classification=classification,
                                  source='synthetic test source', source_hash='a'*64,
                                  observed_at=T, valid_until=T+timedelta(minutes=5))
    return BrokerProfile(identity=identity, symbols=(symbol,), evidence=(evidence,),
                         observed_at=T, valid_until=T+timedelta(hours=1))


def resolve(p, **overrides):
    args=dict(authenticated_identity=p.identity, approved_hash=p.hash, now=T)
    args.update(overrides)
    return p.capability('NAS100', 'BUY_LIMIT_GTD', **args)


def test_two_brokers_same_alias_and_id_do_not_share_contract_or_pin():
    a, b = profile(), profile('Example Broker', '0.1', '10')
    assert a.symbols[0].native_symbol == b.symbols[0].native_symbol
    assert a.symbols[0].contract_value_per_unit != b.symbols[0].contract_value_per_unit
    assert a.hash != b.hash
    with pytest.raises(ValueError, match='pin'): resolve(b, approved_hash=a.hash)
    with pytest.raises(ValueError, match='identity'): resolve(a, authenticated_identity=b.identity)


@pytest.mark.parametrize('field,value', [('broker','Other'),('account_id','other'),
    ('environment','live'),('currency','GBP'),('account_type','NETTED')])
def test_each_identity_component_is_bound(field, value):
    p=profile()
    with pytest.raises(ValueError, match='identity'):
        resolve(p, authenticated_identity=p.identity.model_copy(update={field:value}))


@pytest.mark.parametrize('classification,state,expected', [
    ('synthetic','supported','unknown'), ('protocol','supported','unknown'),
    ('broker_verified','supported','supported'), ('demo_observed','unsupported','unsupported'),
    ('broker_verified','unknown','unknown')])
def test_evidence_classification_and_three_states(classification,state,expected):
    assert resolve(profile(classification=classification,state=state)) == expected


def test_stale_or_future_evidence_and_missing_operation_are_unknown():
    p=profile(classification='broker_verified')
    assert resolve(p, now=T+timedelta(minutes=5)) == 'unknown'
    future=p.evidence[0].model_copy(update={'observed_at':T+timedelta(seconds=1)})
    p=p.model_copy(update={'evidence':(future,)})
    assert resolve(p) == 'unknown'
    assert p.capability('NAS100','CLOSE',authenticated_identity=p.identity,approved_hash=p.hash,now=T)=='unknown'


@pytest.mark.parametrize('now',[T-timedelta(seconds=1),T+timedelta(hours=1)])
def test_profile_outside_validity_rejected(now):
    with pytest.raises(ValueError,match='validity'): resolve(profile(),now=now)


def test_foreign_evidence_and_unchecked_copy_rejected():
    a,b=profile(),profile('Other')
    poisoned=a.model_copy(update={'evidence':b.evidence})
    with pytest.raises(ValueError,match='foreign'): resolve(poisoned)
    bad=a.evidence[0].model_copy(update={'symbol_id':2})
    with pytest.raises(ValueError,match='foreign'): resolve(a.model_copy(update={'evidence':(bad,)}))


def test_duplicates_unknown_mapping_and_invalid_geometry():
    p=profile()
    for update in ({'symbols':p.symbols*2},{'evidence':p.evidence*2}):
        with pytest.raises(ValueError): resolve(p.model_copy(update=update))
    with pytest.raises(ValueError,match='unmapped'):
        p.capability('GOLD','CLOSE',authenticated_identity=p.identity,approved_hash=p.hash,now=T)
    with pytest.raises(ValueError): SymbolMapping.model_validate_json(p.symbols[0].model_copy(update={'maximum':Decimal('0.005')}).model_dump_json())


def test_immutable_roundtrip_and_schema_version():
    p=profile()
    assert BrokerProfile.model_validate_json(p.model_dump_json()).hash==p.hash
    with pytest.raises(ValidationError): p.identity.broker='Other'
    with pytest.raises(ValidationError): p.symbols[0].symbol_id=2
    with pytest.raises(ValueError): resolve(p.model_copy(update={'version':2}))
