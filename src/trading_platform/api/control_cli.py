import json
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlparse


def control(url,token_file,id,action):
    parsed=urlparse(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname: raise ValueError('API URL required')
    token=Path(token_file).read_text().strip()
    request=Request(url.rstrip('/')+'/controls',data=json.dumps({'id':id,'action':action}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=5) as response: return json.load(response)
