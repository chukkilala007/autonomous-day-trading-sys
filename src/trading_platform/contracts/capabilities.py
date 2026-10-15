def require_capabilities(required, available):
    missing=set(required)-set(available)
    if missing: raise ValueError('unsupported capabilities: '+','.join(sorted(missing)))
