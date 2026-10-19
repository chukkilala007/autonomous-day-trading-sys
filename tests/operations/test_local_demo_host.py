import copy
import runpy

qualify = runpy.run_path('scripts/local_demo_host.py')['qualify']


def inputs():
    info = {'OSType': 'linux', 'Architecture': 'aarch64', 'NCPU': 4, 'MemTotal': 4 * 1024**3}
    image = {'Id': 'sha256:' + 'a' * 64, 'Os': 'linux', 'Architecture': 'arm64', 'Config': {'User': '10001:10001'}}
    return info, {'runtime': copy.deepcopy(image), 'gateway': copy.deepcopy(image)}


def test_exact_local_pins_without_registry_or_order_activation():
    report, override = qualify(*inputs())
    assert report['passed'] and not report['orders_enabled']
    assert len(override['services']) == 4
    assert all(v == {'image': 'sha256:' + 'a' * 64, 'pull_policy': 'never'} for v in override['services'].values())
    assert 'explicit_demo_order_authorization' in report['remaining_gates']


def test_host_and_image_failures_produce_no_launch_override():
    info, images = inputs()
    info.update(OSType='windows', NCPU=1, MemTotal=1)
    images['gateway'].update(Id='mutable:latest', Architecture='amd64')
    images['runtime']['Config']['User'] = 'root'
    report, override = qualify(info, images)
    assert not report['passed'] and override is None
    assert set(report['blockers']) == {'LINUX_CONTAINERS_REQUIRED', 'INSUFFICIENT_DOCKER_RESOURCES',
        'GATEWAY_IMAGE_ID_INVALID', 'GATEWAY_NATIVE_IMAGE_REQUIRED', 'RUNTIME_NONROOT_IMAGE_REQUIRED'}
