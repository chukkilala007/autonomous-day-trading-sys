"""Only reviewed, digest-bound packages may be loaded. No dynamic user modules."""
import hashlib
import importlib
import sys
import importlib.metadata
from pathlib import Path
from trading_platform.contracts.capabilities import require_capabilities


def package_digest(path):
    root=Path(path)
    h=hashlib.sha256()
    paths=sorted(root.rglob('*.py')) if root.is_dir() else [root]
    for p in paths:
        h.update((str(p.relative_to(root)) if root.is_dir() else p.name).encode())
        h.update(b'\0');h.update(p.read_bytes())
    return h.hexdigest()


_LOADED = {}


class Registry:
    def __init__(self, reviewed, capabilities=('protected',)):
        # Mapping of package identity to reviewed Manifest, configured by the host.
        self.reviewed=dict(reviewed)
        self.capabilities=capabilities
        self.instances={}

    def load(self, instance):
        if instance.instance_id in self.instances: raise ValueError('duplicate instance')
        manifest=self.reviewed.get(instance.strategy)
        if manifest is None: raise ValueError('unreviewed package')
        if manifest.package != instance.strategy or manifest.digest != instance.package_digest:
            raise ValueError('package digest/version mismatch')
        require_capabilities(manifest.capabilities,self.capabilities)
        for dependency, expected in manifest.dependencies:
            if importlib.metadata.version(dependency) != expected:
                raise ValueError('dependency version mismatch: '+dependency)
        module_name, name=manifest.entrypoint.split(':')
        # Locate source without importing potentially changed plugin code first.
        relative=Path(*module_name.split('.'))
        candidates=[Path(base)/relative.with_suffix('.py') for base in sys.path]
        candidates += [Path(base)/relative/'__init__.py' for base in sys.path]
        path=next((p for p in candidates if p.is_file()),None)
        if path is None: raise ValueError('reviewed source package not found')
        if package_digest(path.parent)!=manifest.digest: raise ValueError('installed package digest mismatch')
        if module_name in _LOADED and _LOADED[module_name]!=manifest.digest:
            raise ValueError('changed package requires worker restart')
        module=importlib.import_module(module_name)
        _LOADED[module_name]=manifest.digest
        plugin=getattr(module,name)()
        for method in ('initialize','evaluate','validate_proposal','migrate_state'):
            if not callable(getattr(plugin,method,None)): raise ValueError('incomplete protocol: '+method)
        self.instances[instance.instance_id]=(instance,manifest,plugin)
        return plugin
