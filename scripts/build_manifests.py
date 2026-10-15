"""Explicitly refresh reviewed fixture hashes after reviewing strategy changes."""
import json
from pathlib import Path
from trading_platform.registry.loader import package_digest
root=Path(__file__).resolve().parents[1]
rows=[]
for name,version,cls,events in [('tpr1','1','TPR',['bar','timer']),('timer_fixture','1','Timer',['bar','timer'])]:
    h=package_digest(root/'src/trading_platform/strategies'/name)
    rows.append(dict(package=name+'@'+version,digest=h,entrypoint=f'trading_platform.strategies.{name}.adapter:{cls}',subscriptions=events))
    instance=dict(instance_id=name,strategy=name+'@'+version,package_digest=h,mode='paper',universe=['XAUUSD' if name=='tpr1' else 'TEST'],account=dict(alias='paper',environment='paper'),allocation='0.005')
    (root/'config/instances'/f'{name}.json').write_text(json.dumps(instance,indent=2)+'\n')
(root/'config/registry.json').write_text(json.dumps(rows,indent=2)+'\n')
