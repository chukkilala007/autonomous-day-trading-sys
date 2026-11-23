import copy,json
from datetime import timedelta
import pytest
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import digest,utc
from trading_platform.gateways.ctrader.pilot import PilotMandate,PilotGate
from trading_platform.gateways.ctrader.pilot_preflight import check
from trading_platform.persistence.database import Database

T=utc('2026-01-01T00:00:00Z')


def fixture(db):
    entry=Entry(instrument='NAS100',side='buy',order_type='limit',entry='100',worst_fill='100',
                stop='99',target='102',expires_at=T+timedelta(seconds=30))
    decision=Decision(instance='scalper',account='demo-account',environment='demo',package='strategy-n@7',
        config_hash='a'*64,event_id='event',snapshot_hash='snapshot',at=T,outcome='ENTRY',proposal=entry)
    command=dict(id=decision.id,instance='scalper',instrument='NAS100',body=dict(type='entry',
        decision=json.loads(decision.model_dump_json()),size=dict(quantity='.01',risk='2.25')))
    mandate=PilotMandate(account_id='12',account_alias='demo-account',test_id='pilot-1',instance='scalper',
        package='strategy-n@7',config_hash='a'*64,instrument='NAS100',quantity='.01',maximum_loss='2.25',
        maximum_stop_distance='2',minimum_reward_risk='2',maximum_decision_age_seconds=2,
        maximum_proposal_lifetime_seconds=60,valid_from=T-timedelta(seconds=1),submit_before=T+timedelta(seconds=10),
        reviewed_bundle_hash='b'*64,source_hash='c'*64,image_digest='d'*64)
    return command,mandate,PilotGate(db,mandate,approved_hash=digest(mandate))


def test_one_fresh_reviewed_strategy_decision_consumes_pilot_before_transport(tmp_path):
    with Database(tmp_path/'db') as db:
        command,mandate,gate=fixture(db)
        assert gate.validate(command,T).id==command['id']
        record=gate.consume(command,T)
        assert record['test_id']=='pilot-1' and record['command_id']==command['id']
        assert db.connection.execute("SELECT 1 FROM checkpoints WHERE id='autonomous-pilot-entry:12'").fetchone()
        with pytest.raises(ValueError,match='already consumed'):gate.validate(command,T)


@pytest.mark.parametrize('fault',['instance','package','config','environment','account','id','quantity','risk','stale','lifetime','geometry','profile'])
def test_pilot_rejects_decision_or_risk_drift_without_consumption(tmp_path,fault):
    with Database(tmp_path/'db') as db:
        command,mandate,gate=fixture(db);raw=copy.deepcopy(command);now=T
        if fault=='instance':raw['instance']='other'
        elif fault=='package':raw['body']['decision']['package']='other@1'
        elif fault=='config':raw['body']['decision']['config_hash']='f'*64
        elif fault=='environment':raw['body']['decision']['environment']='live'
        elif fault=='account':raw['body']['decision']['account']='other'
        elif fault=='id':raw['id']='other'
        elif fault=='quantity':raw['body']['size']['quantity']='.02'
        elif fault=='risk':raw['body']['size']['risk']='2.26'
        elif fault=='stale':now=T+timedelta(seconds=3)
        elif fault=='lifetime':raw['body']['decision']['proposal']['expires_at']=(T+timedelta(seconds=61)).isoformat()
        elif fault=='geometry':raw['body']['decision']['proposal']['target']='101.5'
        elif fault=='profile':raw['body']['decision']['proposal']['profile']='unprotected'
        with pytest.raises(ValueError):gate.validate(raw,now)
        assert not db.connection.execute("SELECT 1 FROM checkpoints WHERE id='autonomous-pilot-entry:12'").fetchone()


def test_pilot_pin_window_and_maximum_loss_are_fail_closed(tmp_path):
    with Database(tmp_path/'db') as db:
        command,mandate,gate=fixture(db)
        with pytest.raises(ValueError,match='pin mismatch'):PilotGate(db,mandate,approved_hash='f'*64)
        with pytest.raises(ValueError,match='window closed'):gate.validate(command,T+timedelta(seconds=10))
        with pytest.raises(ValueError):PilotMandate.model_validate_json(mandate.model_dump_json().replace('"2.25"','"5.01"',1))


def test_preflight_binds_strategy_instance_to_reviewed_broker_bundle(tmp_path):
    from trading_platform.contracts.config import Instance
    from trading_platform.gateways.ctrader.attended_binding import ReviewedBundle
    from trading_platform.gateways.ctrader.demo_configuration import DemoConfiguration
    from trading_platform.gateways.ctrader.modeled_risk import DemoRiskPolicy
    from trading_platform.gateways.ctrader.broker_profile import BrokerProfile,AccountIdentity,SymbolMapping
    with Database(tmp_path/'unused') as db:
        command,mandate,_=fixture(db)
    identity=AccountIdentity(environment='demo',account_id='12',broker='Any',currency='USD',account_type='HEDGED')
    symbol=SymbolMapping(instrument='NAS100',native_symbol='N',symbol_id=1,quote_currency='USD',tick='.01',minimum='.01',maximum='1',step='.01',contract_value_per_unit='1')
    profile=BrokerProfile(identity=identity,symbols=(symbol,),observed_at=T-timedelta(seconds=2),valid_until=T+timedelta(seconds=20))
    policy=DemoRiskPolicy(classification='demo_modeled_risk',cost_coverage='reviewed_fees_plus_explicit_assumptions',account_id='12',instrument='NAS100',symbol_id=1,currency='USD',quote_currency='USD',tick='.01',minimum='.01',maximum='1',step='.01',contract_value_per_unit='1',fee_per_unit='0',minimum_fee='0',fixed_fee='0',adverse_exit_price_allowance='1',other_cost_allowance='0',fee_evidence_hash='f'*64,assumptions_review_hash='1'*64,evidence_hash='2'*64,observed_at=T-timedelta(seconds=2),valid_until=T+timedelta(seconds=20),realized_loss_bounded=False)
    assumptions={k:'configured' for k in ('price_grid','contract_value','fees','financing_adjustments','protection','expiry','recovery')}
    config=DemoConfiguration(classification='operator_configured_demo_trial',identity=identity,instrument='NAS100',symbol_id=1,operations=('BUY_LIMIT_ABSOLUTE_SLTP_GTD_60S','CANCEL_PENDING','CLOSE_POSITION'),assumptions=assumptions,observed_at=T-timedelta(seconds=2),valid_until=T+timedelta(seconds=20),review_hash='3'*64)
    bundle=ReviewedBundle(demo_configuration=config,policy=policy,source_hash='c'*64,image_digest='d'*64,price_grid_review='4'*64,protection_review='5'*64,costs_review='6'*64,entry_expiry_review='7'*64,profile='USD_linear_absolute_protected_buy_limit_gtd',quantity='.01',contract_value_review='8'*64,broker_profile=profile,broker_profile_hash=digest(profile))
    mandate=mandate.model_copy(update={'reviewed_bundle_hash':digest(bundle)})
    instance=Instance(instance_id='scalper',strategy='strategy-n@7',package_digest='package',mode='demo',universe=('NAS100',),account=dict(alias='demo-account',environment='demo',currency='USD',broker_account='12',total_risk='.001',per_trade='.0005',concentration='.0005'),allocation='.0005')
    mandate=mandate.model_copy(update={'config_hash':instance.hash})
    result=check(mandate,instance,bundle,approved_mandate_hash=digest(mandate),approved_bundle_hash=digest(bundle),now=T)
    assert result['status']=='PREPARED_DISABLED' and result['orders_enabled'] is False
    with pytest.raises(ValueError):check(mandate.model_copy(update={'instance':'other'}),instance,bundle,approved_mandate_hash=digest(mandate.model_copy(update={'instance':'other'})),approved_bundle_hash=digest(bundle),now=T)
