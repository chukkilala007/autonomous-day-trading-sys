"""Host-side Docker drill. Explicit images, no network/credentials, temporary state only."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import uuid


def docker(*args, expected=0):
    result=subprocess.run(['docker',*map(str,args)],capture_output=True,text=True,timeout=60)
    if result.returncode!=expected:
        raise RuntimeError(f'Docker {args[0]} exit {result.returncode}: {result.stderr} {result.stdout}')
    return result.stdout.strip()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--baseline',required=True)
    p.add_argument('--candidate',required=True)
    args=p.parse_args()
    images={k:docker('image','inspect',v,'--format','{{.Id}}')
            for k,v in vars(args).items()}
    if images['baseline']==images['candidate']:
        raise ValueError('distinct baseline/candidate images required')
    tests=Path('tests/broker').resolve()
    outcomes=[]
    with tempfile.TemporaryDirectory(prefix='attended-container-') as folder:
        for scenario in ('pending','cancel','close'):
            root=Path(folder)/scenario;root.mkdir(mode=0o777);root.chmod(0o777)
            name='attended-drill-'+uuid.uuid4().hex[:12]
            def create(image,phase,container):
                return docker('create','--init','--name',container,'--network','none','--read-only',
                    '--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges',
                    '-v',f'{root}:/state','-v',f'{tests}:/drill:ro',image,
                    'python','/drill/attended_crash_worker.py','/state',phase,scenario)
            create(args.baseline,'auto',name)
            try:
                docker('start','-a',name,expected=137)
                # Start the exact stopped container again, same retained state.
                docker('start','-a',name)
                original=json.loads((root/'recovery.json').read_text())
            finally:
                docker('rm','-f',name)
            if scenario=='close':
                for label,image in [('upgrade',args.candidate),('rollback',args.baseline)]:
                    replacement=name+'-'+label
                    create(image,'recover',replacement)
                    try:
                        docker('start','-a',replacement)
                        assert json.loads((root/'recovery.json').read_text())==original
                    finally:
                        docker('rm','-f',replacement)
            writes=[json.loads(line)['name'] for line in (root/'wire.jsonl').read_text().splitlines()]
            expected=['ProtoOANewOrderReq','ProtoOAClosePositionReq' if scenario=='close' else 'ProtoOACancelOrderReq']
            assert writes==expected
            outcomes.append(dict(scenario=scenario,container_restart=True,
                upgrade_and_rollback=scenario=='close',writes=writes,**original))
    print(json.dumps(dict(passed=True,images=images,scenarios=outcomes,
        scope='Synthetic broker; exact-container restart plus compatible image replacement; no schema migration or broker connection'),indent=2))


if __name__=='__main__':
    main()
