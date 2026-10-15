import ast,json,sys
from pathlib import Path
import pytest
from trading_platform.registry.loader import Registry,package_digest
from trading_platform.registry.manifest import Manifest
from trading_platform.contracts.config import Instance


def test_two_packages_and_rejections():
    root=Path(__file__).parents[1]/'fixtures/plugins'
    sys.path.insert(0,str(root))
    h=package_digest(root)
    manifests={n:Manifest(package=n,digest=h,entrypoint='plugin:'+cls,subscriptions=('timer',)) for n,cls in [('first@1','First'),('second@1','Second')]}
    r=Registry(manifests)
    def instance(n='first@1',d=h):
        return Instance.model_validate_json(json.dumps(dict(instance_id=n,strategy=n,package_digest=d,mode='paper',universe=['X'],account=dict(alias='p',environment='paper'),allocation='0.005')))
    bad=manifests['first@1'].model_copy(update={'dependencies':(('pydantic','0.0'),)})
    with pytest.raises(ValueError): Registry({'first@1':bad}).load(instance())
    assert r.load(instance())
    assert r.load(instance('second@1'))
    with pytest.raises(ValueError): r.load(instance())
    with pytest.raises(ValueError): Registry(manifests).load(instance(d='bad'))
    with pytest.raises(ValueError): Registry(manifests,capabilities=()).load(instance())


def test_shared_code_has_no_concrete_strategy_import():
    root=Path('src/trading_platform')
    for p in root.rglob('*.py'):
        if 'strategies' in p.parts: continue
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node,ast.ImportFrom): assert '.strategies.' not in (node.module or '')
            if isinstance(node,ast.Import): assert all('.strategies.' not in n.name for n in node.names)
