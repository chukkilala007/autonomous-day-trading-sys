"""Generate private analysis configuration/tokens; never accepts broker secrets."""
import argparse,json,secrets
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--account',required=True);p.add_argument('--symbol',required=True);p.add_argument('--destination',default='var/shadow-analysis');a=p.parse_args()
    if not a.account.isdigit() or int(a.account)<=0: raise ValueError('explicit demo account ID required')
    root=Path(a.destination);root.mkdir(parents=True,mode=0o700,exist_ok=False)
    for name in ('gateway','tpr1','timer_fixture','reader'):
        file=root/(name+'.token');file.write_text(secrets.token_urlsafe(48)+'\n');file.chmod(0o600)
    for name in ('tpr1','timer_fixture'):
        data=json.loads(Path('config/instances/'+name+'.json').read_text());data['mode']='shadow';data['universe']=[a.symbol]
        data['account'].update(alias='demo-shadow',environment='demo',broker_account=a.account)
        (root/(name+'.json')).write_text(json.dumps(data,indent=2))
    deployment={'registry':'/app/config/registry.json','instances':['/analysis/tpr1.json','/analysis/timer_fixture.json'],
        'gateway':{'host':'shadow-gateway'},'workers':{'tpr1':{'host':'shadow-tpr'},'timer_fixture':{'host':'shadow-timer'}},
        'tokens':{name:'/run/secrets/'+name+'_token' for name in ('gateway','tpr1','timer_fixture')},'api':{'reader_token':'/run/secrets/reader_token','port':9010}}
    (root/'deployment.json').write_text(json.dumps(deployment,indent=2));print('Created private analysis configuration; no broker authorization or order capability enabled.')

if __name__=='__main__': main()
