"""Import a private sandbox token document without logging credential values."""
import argparse,json,os,re,subprocess
from pathlib import Path


def tokens(text):
    lines=[s.strip() for s in text.splitlines() if s.strip()]
    result={}
    for label,key in [('Access Token','access_token'),('Refresh Token','refresh_token')]:
        indices=[i for i,line in enumerate(lines) if line.casefold()==label.casefold()]
        if len(indices)!=1 or indices[0]+1>=len(lines): raise ValueError('missing or duplicate token label')
        value=lines[indices[0]+1]
        if not re.fullmatch(r'[A-Za-z0-9._~-]{16,4096}',value): raise ValueError('invalid token format')
        result[key]=value
    # Relative expiry from a copied document is not a trustworthy absolute time.
    # Force authenticated refresh; never guess when the document was generated.
    return dict(result,expires_at=0)


def private(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077:
        raise ValueError('private regular credential file required')
    return path


def load_document(path):
    path=private(path)
    if path.suffix.lower()=='.rtf':
        return subprocess.check_output(['textutil','-convert','txt','-stdout',str(path)],text=True,stderr=subprocess.DEVNULL)
    return path.read_text()


def main():
    p=argparse.ArgumentParser();p.add_argument('--document',required=True);p.add_argument('--application',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    try:
        value=tokens(load_document(a.document));app=json.loads(private(a.application).read_text())
        for key in ('client_id','client_secret'):
            if not isinstance(app.get(key),str) or not app[key].strip(): raise ValueError('application credentials incomplete')
            value[key]=app[key]
        fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out: json.dump(value,out);out.flush();os.fsync(out.fileno())
    except Exception:
        raise SystemExit('Sandbox import failed; check private input files, labels and exclusive destination. No credential values logged.') from None
    print('Private credential bundle created; demo account binding is required before use.')

if __name__=='__main__': main()
