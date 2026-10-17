"""Generate private analysis configuration/tokens; never accepts broker secrets."""
import argparse,json,secrets
from pathlib import Path
from datetime import datetime,timezone
from trading_platform.contracts.config import Instance
from trading_platform.registry.manifest import Manifest
from trading_platform.gateways.ctrader.metadata import CapabilityReport
from trading_platform.gateways.ctrader.feed_config import build


def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True);p.add_argument('--account',required=True);p.add_argument('--symbol',required=True);p.add_argument('--destination',default='var/shadow-analysis');a=p.parse_args()
    if not a.account.isdigit() or int(a.account)<=0: raise ValueError('explicit demo account ID required')
    probe=json.loads(Path(a.probe).read_text())
    if probe.get('status')!='COLLECTED' or probe.get('account_id')!=a.account:raise ValueError('bound collected probe required')
    reports={name:CapabilityReport.model_validate_json(json.dumps(value['capability'])) for name,value in probe['capability_audit']['symbols'].items()}
    manifests={m['package']:Manifest.model_validate_json(json.dumps(m)) for m in json.loads(Path('config/registry.json').read_text())}
    instances=[]
    for name in ('tpr1','timer_fixture'):
        data=json.loads(Path('config/instances/'+name+'.json').read_text());data['mode']='shadow';data['universe']=[a.symbol]
        data['account'].update(alias='demo-shadow',environment='demo',broker_account=a.account,currency=probe['economics']['account']['currency'])
        instances.append(Instance.model_validate_json(json.dumps(data)))
    feed=build(instances,manifests,reports,a.account,datetime.now(timezone.utc))
    root=Path(a.destination);root.mkdir(parents=True,mode=0o700,exist_ok=False)
    for name in ('gateway','tpr1','timer_fixture','reader'):
        file=root/(name+'.token');file.write_text(secrets.token_urlsafe(48)+'\n');file.chmod(0o600)
    for instance in instances:
        (root/(instance.instance_id+'.json')).write_text(instance.model_dump_json(indent=2))
    (root/'feed.json').write_text(json.dumps(feed,indent=2))
    deployment={'registry':'/app/config/registry.json','instances':['/analysis/tpr1.json','/analysis/timer_fixture.json'],
        'gateway':{'host':'shadow-gateway'},'workers':{'tpr1':{'host':'shadow-tpr'},'timer_fixture':{'host':'shadow-timer'}},
        'tokens':{name:'/run/secrets/'+name+'_token' for name in ('gateway','tpr1','timer_fixture')},'api':{'reader_token':'/run/secrets/reader_token','port':9010}}
    (root/'deployment.json').write_text(json.dumps(deployment,indent=2));print('Created private analysis configuration; no broker authorization or order capability enabled.')

if __name__=='__main__': main()
