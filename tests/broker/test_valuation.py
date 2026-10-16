import copy,json
from datetime import datetime,timezone,timedelta
import pytest
from trading_platform.gateways.ctrader.valuation import export

T=datetime(2026,10,16,tzinfo=timezone.utc)

def fixture():
    return dict(mode='demo',account_id='12',observed_at=T.isoformat(),classification='demo_observed',evidence_hash='a'*64,
        currency='GBP',balance='10000',equity='9999',free_margin='9000',history_complete=True,external_exposure=False,contracts={},
        settlements=[dict(command_id='c',position_id='p',opened='2',closed='2',complete=True,costs_complete=True,
            history_from=(T-timedelta(days=1)).isoformat(),opened_at=(T-timedelta(hours=2)).isoformat(),closed_at=(T-timedelta(hours=1)).isoformat(),history_to=T.isoformat(),evidence_hash='b'*64,
            movements=[dict(id=str(i),position_id='p',currency='GBP',amount=n,evidence_hash='c'*64) for i,n in enumerate(['10','-1','-2','-.5'])])])


def test_net_includes_open_close_costs_and_never_rounds():
    value=export(json.dumps(fixture()),'12',T)
    assert value['settlements']['c']['net']=='6.5'
    assert value['account']['equity']=='9999'
    assert len(value['evidence_hash'])==64


@pytest.mark.parametrize('mutation',[
    lambda v:v.update(account_id='13'),lambda v:v.update(balance=1.1),
    lambda v:v.update(observed_at=(T-timedelta(seconds=3)).isoformat()),
    lambda v:v['settlements'][0].update(closed='1'),lambda v:v['settlements'][0].update(costs_complete=False),
    lambda v:v['settlements'][0].update(history_from=T.isoformat()),
    lambda v:v['settlements'][0]['movements'][0].update(currency='USD'),
    lambda v:v['settlements'][0]['movements'][0].update(position_id='foreign'),
    lambda v:v['settlements'][0]['movements'].append(copy.deepcopy(v['settlements'][0]['movements'][0])),
    lambda v:v['settlements'].append(copy.deepcopy(v['settlements'][0])),
    lambda v:v['settlements'][0].update(movements=[]),
])
def test_invalid_economics_never_export(mutation):
    value=fixture();mutation(value)
    with pytest.raises(ValueError): export(json.dumps(value),'12',T)
