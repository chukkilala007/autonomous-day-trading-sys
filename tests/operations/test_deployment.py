import runpy
import pytest


def test_release_manifest_requires_immutable_digest():
    module=runpy.run_path('scripts/release_manifest.py')
    with pytest.raises(ValueError): module['manifest']('example/image:latest')
    result=module['manifest']('registry.example/trading@sha256:'+'a'*64)
    assert len(result['services'])==6
    assert all(v['pull_policy']=='always' for v in result['services'].values())
