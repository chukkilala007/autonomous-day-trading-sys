import copy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import pytest
from trading_platform.gateways.ctrader.settlement import CostPolicy,settle
T=datetime(2026,10,16,tzinfo=timezone.utc)


def fixture():
    policy=CostPolicy(account_id='12',evidence_hash='a'*64,verified_at=T-timedelta(days=1),valid_until=T+timedelta(days=1),commission_sign='positive_charge',conversion_fee_sign='positive_charge',closing_commission_source='close_detail',closing_commission_excludes_opening=True,all_costs_covered=True)
    base=dict(positionId='2',symbolId='1',filledVolume='200',dealStatus='FILLED',moneyDigits=2,commission='100')
    opened=dict(base,dealId='1',orderId='3',tradeSide='BUY',executionTimestamp=str(int((T-timedelta(hours=2)).timestamp()*1000)))
    closed=dict(base,dealId='2',orderId='4',tradeSide='SELL',executionTimestamp=str(int((T-timedelta(hours=1)).timestamp()*1000)),closePositionDetail=dict(closedVolume='200',grossProfit='1000',swap='-25',commission='150',pnlConversionFee='50',moneyDigits=2))
    return policy,[opened,closed]


def call(policy,deals):
    return settle('12',{'id':'cmd','currency':'GBP'},'2','3',Decimal(2),deals,T-timedelta(days=1),T,T,policy)


def test_raw_deals_include_opening_costs_and_do_not_double_count_close_commission():
    result=call(*fixture())
    assert sum(m.amount for m in result.movements)==Decimal('6.75')
    assert len(result.movements)==5


@pytest.mark.parametrize('fault',['missing_open','missing_fee','duplicate','partial','scale_in','foreign','expired','side','negative_charge'])
def test_incomplete_or_ambiguous_settlement_rejected(fault):
    policy,deals=fixture()
    if fault=='missing_open': deals=deals[1:]
    if fault=='missing_fee': del deals[1]['closePositionDetail']['pnlConversionFee']
    if fault=='duplicate': deals.append(copy.deepcopy(deals[0]))
    if fault=='partial': deals[1]['filledVolume']='100';deals[1]['closePositionDetail']['closedVolume']='100'
    if fault=='scale_in': deals[0]['orderId']='99'
    if fault=='foreign': policy=policy.model_copy(update={'account_id':'99'})
    if fault=='expired': policy=policy.model_copy(update={'valid_until':T})
    if fault=='side': deals[1]['tradeSide']='BUY'
    if fault=='negative_charge': deals[0]['commission']='-1'
    with pytest.raises((ValueError,KeyError)): call(policy,deals)
