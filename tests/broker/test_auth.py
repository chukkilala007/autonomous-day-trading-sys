import json
import pytest
from trading_platform.gateways.ctrader.auth import TokenStore, bind_demo


def test_rotated_credentials_survive_restart_and_invalid_refresh(tmp_path):
    seed=tmp_path/'seed'; rotated=tmp_path/'private'/'tokens'
    seed.write_text(json.dumps(dict(client_id='synthetic',client_secret='test',access_token='old',refresh_token='old-refresh',expires_at=1)))
    seed.chmod(0o600);store=TokenStore(seed,rotated)
    original=store.read()
    store.rotate(original,dict(accessToken='new',refreshToken='new-refresh',expiresIn=60),10)
    assert TokenStore(seed,rotated).read()['access_token']=='new'
    assert rotated.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError): store.rotate(original,{},10)
    assert store.read()['refresh_token']=='new-refresh'
    seed.chmod(0o644)
    with pytest.raises(ValueError): TokenStore(seed,tmp_path/'missing').read()


def test_account_binding_rejects_unknown_live_and_duplicate():
    assert bind_demo([dict(ctidTraderAccountId='12',isLive=False)],12)
    for accounts in ([],[dict(ctidTraderAccountId='12',isLive=True)],[dict(ctidTraderAccountId='12')],2*[dict(ctidTraderAccountId='12',isLive=False)]):
        with pytest.raises(ValueError): bind_demo(accounts,12)
