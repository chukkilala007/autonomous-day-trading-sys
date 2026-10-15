"""Check resolved deployment isolation, not string matching of YAML source."""
import json,subprocess


def audit(config):
    services=config['services']
    for name in ('core','worker-tpr','worker-timer','simulator','dashboard'):
        service=services[name]
        assert service['user']=='10001:10001',name
        assert service['read_only'] and 'ALL' in service['cap_drop'],name
        assert any('no-new-privileges' in v for v in service['security_opt']),name
        assert service.get('pids_limit') and service.get('mem_limit'),name
        if name!='dashboard': assert not service.get('ports'),name
    assert all(p['host_ip']=='127.0.0.1' for p in services['dashboard']['ports'])
    for name in ('worker-tpr','worker-timer','dashboard'):
        assert not services[name].get('volumes'),name
    for name in ('worker-tpr','worker-timer'):
        assert set(services[name]['networks'])=={'workers'}
        assert len(services[name]['secrets'])==1
    assert all(n.get('internal') for n in config['networks'].values())
    return {'isolation':'PASS','services':5}


if __name__=='__main__':
    config=json.loads(subprocess.check_output(['docker','compose','--profile','ui','config','--format','json'],text=True))
    print(json.dumps(audit(config)))
