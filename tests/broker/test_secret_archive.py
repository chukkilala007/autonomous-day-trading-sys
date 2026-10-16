import os
import pytest
pytest.importorskip('cryptography')
from trading_platform.persistence.secret_archive import backup,restore,exclusive_write


def test_encrypted_restore_tamper_wrong_key_and_no_overwrite(tmp_path):
    key=tmp_path/'key';secret=tmp_path/'tokens';archive=tmp_path/'sealed'
    exclusive_write(key,os.urandom(32));exclusive_write(secret,b'{"access_token":"synthetic-secret"}')
    assert backup(key,{'tokens.json':secret},archive)['encrypted']
    assert b'synthetic-secret' not in archive.read_bytes()
    restored=tmp_path/'isolated';assert restore(key,archive,restored)['broker_activation'] is False
    assert (restored/'tokens.json').read_bytes()==secret.read_bytes()
    assert restored.stat().st_mode & 0o777==0o700
    assert (restored/'tokens.json').stat().st_mode & 0o777==0o600
    with pytest.raises(FileExistsError):restore(key,archive,restored)
    with pytest.raises(FileExistsError):backup(key,{'tokens.json':secret},archive)
    wrong=tmp_path/'wrong';exclusive_write(wrong,os.urandom(32))
    with pytest.raises(ValueError,match='authentication'):restore(wrong,archive,tmp_path/'wrong-restore')
    data=bytearray(archive.read_bytes());data[-1]^=1;archive.write_bytes(data)
    with pytest.raises(ValueError,match='authentication'):restore(key,archive,tmp_path/'corrupt-restore')
    assert not (tmp_path/'corrupt-restore').exists()


def test_secret_archive_rejects_public_files_paths_and_key_inclusion(tmp_path):
    key=tmp_path/'key';secret=tmp_path/'tokens';exclusive_write(key,os.urandom(32));secret.write_text('synthetic')
    with pytest.raises(ValueError,match='private'):backup(key,{'tokens.json':secret},tmp_path/'out')
    secret.chmod(0o600)
    with pytest.raises(ValueError,match='invalid archive name'):backup(key,{'../tokens.json':secret},tmp_path/'out')
    with pytest.raises(ValueError,match='key cannot'):backup(key,{'key.key':key},tmp_path/'out')
    link=tmp_path/'link';link.symlink_to(secret)
    with pytest.raises(OSError):backup(key,{'tokens.json':link},tmp_path/'out')
