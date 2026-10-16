import runpy
import pytest
module=runpy.run_path('scripts/import_sandbox.py')


def test_token_document_never_guesses_absolute_expiry():
    value=module['tokens']('Access Token\n'+'a'*32+'\nRefresh Token\n'+'b'*32+'\nExpires In 10000')
    assert value['expires_at']==0 and len(value['access_token'])==32
    with pytest.raises(ValueError): module['tokens']('Access Token\nshort')
    with pytest.raises(ValueError): module['tokens']('Access Token\n'+'a'*32+'\nAccess Token\n'+'c'*32)


def test_credential_import_rejects_public_or_linked_files(tmp_path):
    path=tmp_path/'creds';path.write_text('synthetic');path.chmod(0o644)
    with pytest.raises(ValueError): module['private'](path)
    path.chmod(0o600);assert module['private'](path)==path
    link=tmp_path/'link';link.symlink_to(path)
    with pytest.raises(ValueError): module['private'](link)
