import pytest
from trading_platform.contracts.config import Instance
import json


def config():
    return dict(instance_id='a',strategy='test@1',package_digest='abc',mode='paper',universe=['X'],account=dict(alias='paper',environment='paper'),allocation='0.005')

def test_mandate():
    a=Instance.model_validate_json(json.dumps(config()))
    assert a.hash and a.submission_enabled
    for patch in [dict(allocation='0.02'),dict(mode='live'),dict(password='secret')]:
        with pytest.raises(ValueError): Instance.model_validate_json(json.dumps(config()|patch))
    shadow=Instance.model_validate_json(json.dumps(config()|{'mode':'shadow'}))
    assert not shadow.submission_enabled

def test_account_binding_required():
    for mode in ('demo','live'):
        data=config()|dict(mode=mode,account=dict(alias='test',environment=mode))
        with pytest.raises(ValueError): Instance.model_validate_json(json.dumps(data))
