"""Derive read-only subscriptions from reviewed strategies and expiring evidence."""
import json
from trading_platform.contracts.config import Instance
from trading_platform.registry.manifest import Manifest
from trading_platform.contracts.values import digest
from .metadata import CapabilityReport

MINUTES={'M1':1,'M5':5,'M15':15,'M30':30,'H1':60,'H4':240,'D1':1440}


def derive(instances,manifests,reports,account,now):
    if not instances or len({i.instance_id for i in instances})!=len(instances):raise ValueError('unique shadow instances required')
    symbols={};requirements={}
    for instance in instances:
        if instance.mode!='shadow' or instance.account.environment!='demo' or instance.account.broker_account!=str(account):
            raise ValueError('shadow account binding mismatch')
        manifest=manifests.get(instance.strategy)
        if not manifest or manifest.digest!=instance.package_digest:raise ValueError('unreviewed strategy manifest')
        if not manifest.history:raise ValueError('explicit strategy history required')
        for symbol in instance.universe:
            report=reports[symbol]
            if report.account_id!=str(account) or report.symbol!=symbol:raise ValueError('foreign feed evidence')
            evidence={e.field:e.value for e in report.evidence if e.classification in ('demo_observed','broker_verified') and e.observed_at<=now<e.valid_until}
            basis=evidence.get('candle_basis');sid=evidence.get('symbol_id','')
            if basis!=manifest.price_basis or not sid.isdigit() or int(sid)<=0:raise ValueError('current symbol and basis evidence required')
            symbols[symbol]=int(sid)
            for timeframe,count in manifest.history:
                if timeframe not in MINUTES or not 0<count<=1000:raise ValueError('unsupported strategy history')
                key=(symbol,basis,MINUTES[timeframe]);requirements[key]=max(requirements.get(key,0),count)
    if len(set(symbols.values()))!=len(symbols):raise ValueError('duplicate symbol identity')
    return dict(symbols=symbols,requirements=[[*key,count] for key,count in sorted(requirements.items())])


def build(instances,manifests,reports,account,now):
    result=derive(instances,manifests,reports,account,now)
    result.update(account_id=str(account),instances=[i.model_dump(mode='json') for i in instances],
                  manifests=[m.model_dump(mode='json') for m in manifests.values()],
                  reports={s:r.model_dump(mode='json') for s,r in reports.items()},history_hours=24)
    result['evidence_hash']=digest(result)
    return result


def validate(config,account,now):
    body={k:v for k,v in config.items() if k!='evidence_hash'}
    if digest(body)!=config.get('evidence_hash') or config.get('account_id')!=str(account):raise ValueError('feed config binding or hash mismatch')
    instances=[Instance.model_validate_json(json.dumps(i)) for i in config['instances']]
    rows=[Manifest.model_validate_json(json.dumps(m)) for m in config['manifests']]
    if len({m.package for m in rows})!=len(rows):raise ValueError('duplicate manifest')
    reports={s:CapabilityReport.model_validate_json(json.dumps(r)) for s,r in config['reports'].items()}
    expected=derive(instances,{m.package:m for m in rows},reports,account,now)
    if any(config[k]!=v for k,v in expected.items()):raise ValueError('feed requirements differ from strategies')
    return expected
