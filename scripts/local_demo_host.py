"""Read-only local Docker host check and exact-image shadow override.

Does not start services, change power settings, inspect secrets or enable orders.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path


SERVICES = {'shadow-gateway': 'gateway', 'shadow-core': 'runtime',
            'shadow-tpr': 'runtime', 'shadow-timer': 'runtime'}


def qualify(info, images):
    blockers = []
    if info.get('OSType') != 'linux':
        blockers.append('LINUX_CONTAINERS_REQUIRED')
    if info.get('NCPU', 0) < 2 or info.get('MemTotal', 0) < 2 * 1024**3:
        blockers.append('INSUFFICIENT_DOCKER_RESOURCES')
    pins = {}
    for role in ('runtime', 'gateway'):
        image = images[role]
        identity = image.get('Id', '')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', identity):
            blockers.append(role.upper() + '_IMAGE_ID_INVALID')
        if image.get('Os') != 'linux':
            blockers.append(role.upper() + '_IMAGE_OS_INVALID')
        aliases = {'aarch64': 'arm64', 'x86_64': 'amd64'}
        host_arch = aliases.get(info.get('Architecture'), info.get('Architecture'))
        if image.get('Architecture') != host_arch:
            blockers.append(role.upper() + '_NATIVE_IMAGE_REQUIRED')
        if image.get('Config', {}).get('User') != '10001:10001':
            blockers.append(role.upper() + '_NONROOT_IMAGE_REQUIRED')
        pins[role] = identity
    report = {'format': 1, 'scope': 'local_docker_prerequisites_only',
              'passed': not blockers, 'blockers': blockers, 'orders_enabled': False,
              'images': pins, 'docker': {k: info.get(k) for k in
                  ('ServerVersion', 'OSType', 'Architecture', 'NCPU', 'MemTotal')},
              'remaining_gates': ['host_awake_during_session', 'fresh_broker_capabilities',
                                  'strategy_shadow_acceptance', 'explicit_demo_order_authorization',
                                  'broker_order_lifecycle_acceptance', 'backup_recovery']}
    override = {'services': {name: {'image': pins[role], 'pull_policy': 'never'}
                             for name, role in SERVICES.items()}} if not blockers else None
    return report, override


def docker(*args):
    return json.loads(subprocess.check_output(['docker', *args], text=True, timeout=30))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-image', required=True)
    parser.add_argument('--gateway-image', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    report, override = qualify(docker('info', '--format', '{{json .}}'),
                              {role: docker('image', 'inspect', name)[0] for role, name in
                               [('runtime', args.runtime_image), ('gateway', args.gateway_image)]})
    root = Path(args.destination)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    (root / 'host-report.json').write_text(json.dumps(report, indent=2) + '\n')
    if override:
        (root / 'images.json').write_text(json.dumps(override, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'blockers': report['blockers'], 'orders_enabled': False}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
