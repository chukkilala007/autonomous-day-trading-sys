"""Only reviewed, digest-bound packages may be loaded. No dynamic user modules."""
import hashlib
import importlib
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
        module=importlib.import_module(module_name)
        root=Path(module.__file__).parent
        if package_digest(root)!=manifest.digest: raise ValueError('installed package digest mismatch')
        plugin=getattr(module,name)()
        for method in ('initialize','evaluate','validate_proposal','migrate_state'):
            if not callable(getattr(plugin,method,None)): raise ValueError('incomplete protocol: '+method)
        self.instances[instance.instance_id]=(instance,manifest,plugin)
        return plugin
