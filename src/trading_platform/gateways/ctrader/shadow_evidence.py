"""Convert only fresh reviewed gateway facts into strategy execution evidence."""
from decimal import Decimal, InvalidOperation


def execution_evidence(reports, now):
    result = {}
    for symbol, report in reports.items():
        current = {row.field: row for row in report.evidence
                   if row.classification in ('demo_observed', 'broker_verified')
                   and row.observed_at <= now < row.valid_until}
        tick = current.get('tick_grid'); basis = current.get('candle_basis'); session = current.get('session_state')
        if not tick or not basis or not session or basis.value not in ('bid', 'ask') or session.value != 'OPEN':
            continue
        if not 0 <= (now-session.observed_at).total_seconds() <= 30: continue
        try:
            parsed = Decimal(tick.value)
            if not parsed.is_finite() or parsed <= 0: continue
        except (InvalidOperation, ValueError):
            continue
        result[symbol] = {
            'tick_size': str(parsed), 'actual_session_open': True,
            'session_source_time': session.observed_at.isoformat(), 'price_basis': basis.value,
            'provenance': {'tick_size': tick.source, 'actual_session_open': session.source,
                           'price_basis': basis.source}}
    return result
