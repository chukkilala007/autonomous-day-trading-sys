"""Isolated Compose restart drill; removes only its own generated test project."""
import json,os,subprocess,tempfile,time,uuid
from pathlib import Path

root=Path(__file__).resolve().parents[1]
project='paper-smoke-'+uuid.uuid4().hex[:10]
with tempfile.TemporaryDirectory() as temporary:
    override=Path(temporary)/'override.json'
    override.write_text(json.dumps({'services':{'core':{'command':['trading-platform','run-paper','--deployment','/app/config/paper-deployment.json','--input','/app/tests/fixtures/paper.json','--state','/state/core.db','--step-delay','8']}}}))
    base=['docker','compose','-p',project,'-f',str(root/'compose.yaml'),'-f',str(override)]
    def run(*args,capture=False):
        return subprocess.run(base+list(args),cwd=root,check=True,text=True,stdout=subprocess.PIPE if capture else None).stdout
    def status():
        return json.loads(run('exec','-T','core','trading-platform','status','--state','/state/core.db',capture=True))
    def wait_for(predicate):
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            try:
                current=status()
                if predicate(current): return current
            except (subprocess.CalledProcessError,json.JSONDecodeError): pass
            time.sleep(.5)
        raise AssertionError('paper stack did not reach expected state')
    try:
        run('up','-d')
        opened=wait_for(lambda s:len(s['orders'])==2 and len(s['active_risk'])==2)
        ids=sorted(o['id'] for o in opened['orders'])
        run('kill','-s','SIGKILL','core')
        run('restart','worker-tpr','worker-timer','simulator')
        run('start','core')
        closed=wait_for(lambda s:len(s['orders'])==2 and all(o['status']=='CLOSED' for o in s['orders']))
        assert sorted(o['id'] for o in closed['orders'])==ids
        assert not closed['positions'] and not closed['active_risk']
        assert all(i['cursor']==4 and not i['halt'] for i in closed['instances'])
        assert not closed['rejections']
        print(json.dumps({'result':'PASS','drill':'core SIGKILL with open exposure; worker and simulator restart','status':closed}))
    finally:
        run('logs','--no-color')
        run('down','--volumes','--remove-orphans')
