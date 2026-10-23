"""Compatibility entry point for the historical FxPro-only specification review.

Generic discovery/valuation never imports this provider. No broker auto-detection.
"""
from .evidence_providers.fxpro import PUBLIC, SOURCES, main, reconcile

__all__ = ['PUBLIC', 'SOURCES', 'main', 'reconcile']

if __name__ == '__main__':
    main()
