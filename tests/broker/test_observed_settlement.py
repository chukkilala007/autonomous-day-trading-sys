import copy,runpy,json
from datetime import timedelta
from decimal import Decimal
import pytest
from trading_platform.contracts.values import digest,canonical
from trading_platform.gateways.ctrader.settlement import ObservedZeroCostPolicy,verify_observed_cash,settle
from trading_platform.gateways.ctrader.management import reconcile_cleanup
from trading_platform.persistence.database import Database
from test_settlement_mapping import T,fixture


def observed():
    _,deals=fixture()
    for d in deals:d['commission']='0'
    detail=deals[1]['closePositionDetail'];detail.update(commission='0',swap='0',pnlConversionFee='0',balance='11000')
    p=ObservedZeroCostPolicy(classification='demo_observed_zero_cost_lifecycle',account_id='12',command_id='cmd',position_id='2',entry_order_id='3',currency='GBP',quantity='2',deals_hash=digest(sorted(deals,key=lambda d:str(d['dealId']))),balance_before='100',balance_after='110',baseline_evidence_hash='a'*64,review_hash='b'*64,history_from=T-timedelta(days=1),verified_at=T-timedelta(minutes=1),valid_until=T+timedelta(days=1))
    e=dict(account_id='12',account=dict(currency='GBP',balance='110'),reconciliation={})
    return p,deals,e


def test_exact_zero_cost_lifecycle_settles_without_general_fee_claim():
    p,deals,e=observed();verify_observed_cash(p,deals,[],e)
    s=settle('12',dict(id='cmd',currency='GBP'),'2','3',Decimal(2),deals,p.history_from,T,T,p)
    assert sum(m.amount for m in s.movements)==10


@pytest.mark.parametrize('fault',['deal','cashflow','balance','position','commission','missing','scope','expired'])
def test_observed_cash_rejects_changed_or_incomplete_evidence(fault):
    p,deals,e=observed();cash=[]
    if fault=='deal':deals[0]['dealId']='foreign'
    if fault=='cashflow':cash=[{'id':'deposit'}]
    if fault=='balance':e['account']['balance']='111'
    if fault=='position':e['reconciliation']['position']=[{'positionId':'9'}]
    if fault=='commission':deals[0]['commission']='1';p=p.model_copy(update={'deals_hash':digest(deals)})
    if fault=='missing':del deals[1]['closePositionDetail']['swap'];p=p.model_copy(update={'deals_hash':digest(deals)})
    if fault=='scope':p=p.model_copy(update={'command_id':'other'})
    if fault=='expired':p=p.model_copy(update={'valid_until':T})
    with pytest.raises(ValueError):
        verify_observed_cash(p,deals,cash,e)
        settle('12',dict(id='cmd',currency='GBP'),'2','3',Decimal(2),deals,p.history_from,T,T,p)


def test_cleanup_requires_owned_settled_target_and_is_idempotent(tmp_path):
    with Database(tmp_path/'db') as db:
        values={'gateway-management:m':dict(status='UNKNOWN',request='ProtoOAClosePositionReq',fields=dict(ctidTraderAccountId=12,positionId=2,volume=200),owner='x',target_quantity='2'),
                'broker-position:2':dict(closed=True,quantity='0',owner='x'),
                'gateway-send:cmd':dict(instance='x')}
        for k,v in values.items():db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',(k,canonical(v)))
        reconcile_cleanup(db,'12',T)
        read=lambda:json.loads(db.connection.execute("SELECT body FROM checkpoints WHERE id='gateway-management:m'").fetchone()[0])
        assert read()['status']=='UNKNOWN'
        s=dict(position_id='2',command_id='cmd',complete=True,costs_complete=True,closed='2')
        db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',('provider-settlement:cmd',canonical(s)))
        reconcile_cleanup(db,'13',T);assert read()['status']=='UNKNOWN'
        reconcile_cleanup(db,'12',T);first=read();assert first['status']=='TARGET_RESOLVED' and first['request_acceptance_confirmed'] is False
        reconcile_cleanup(db,'12',T+timedelta(seconds=1));assert read()==first
