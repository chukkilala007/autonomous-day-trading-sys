import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path('scripts').resolve()))
from release_bundle import build,verify,TOKENS

IMAGE='ghcr.io/example/paper@sha256:'+'a'*64

def repo(tmp_path,monkeypatch):
    root=tmp_path/'repo';root.mkdir()
    for name in {'compose.yaml',*TOKENS}:
        file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('public fixture')
    (root/'.gitignore').write_text('private-token\n')
    (root/'private-token').write_text('MUST NOT PACKAGE')
    names=sorted({'compose.yaml',*TOKENS})
    def fake_git(root,*args):
        if args[0]=='rev-parse': return b'b'*40
        if args[0]=='status': return b' M compose.yaml' if (root/'compose.yaml').read_text()=='dirty' else b''
        if args[0]=='ls-tree': return b'\0'.join(('100644 blob '+str(i)+'\t'+n).encode() for i,n in enumerate(names))
        if args[0]=='cat-file': return (root/names[int(args[2])]).read_bytes()
        raise AssertionError(args)
    monkeypatch.setattr('release_bundle.git',fake_git)
    return root


def test_reproducible_clean_commit_bundle_excludes_local_secrets(tmp_path,monkeypatch):
    root=repo(tmp_path,monkeypatch);one=build(root,tmp_path/'one',IMAGE);two=build(root,tmp_path/'two',IMAGE)
    assert one==two and not (tmp_path/'one/private-token').exists()
    assert verify(tmp_path/'one')['broker_orders_enabled'] is False
    with pytest.raises(FileExistsError): build(root,tmp_path/'one',IMAGE)
    (root/'compose.yaml').write_text('dirty')
    with pytest.raises(ValueError,match='commit'): build(root,tmp_path/'three',IMAGE)


@pytest.mark.parametrize('fault',['tamper','extra','link','incomplete','traversal'])
def test_invalid_bundle_rejected(tmp_path,monkeypatch,fault):
    import json
    root=repo(tmp_path,monkeypatch);dest=tmp_path/'bundle';build(root,dest,IMAGE)
    if fault=='tamper': (dest/'compose.yaml').write_text('modified')
    if fault=='extra': (dest/'secret').write_text('unexpected')
    if fault=='link':
        (dest/'compose.yaml').unlink();(dest/'compose.yaml').symlink_to(root/'compose.yaml')
    if fault=='incomplete': (dest/'INCOMPLETE').write_text('failed')
    if fault=='traversal':
        path=dest/'bundle.json';body=json.loads(path.read_text());body['files']['../outside']='a'*64;path.write_text(json.dumps(body))
    with pytest.raises(ValueError): verify(dest)
