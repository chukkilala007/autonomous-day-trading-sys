"""Bounded historical closure evidence, separate from current trading availability."""
from datetime import timedelta
from trading_platform.contracts.values import digest, utc
from .normalization import integer
from .sessions import scheduled_state


def regular_closed(metadata, start, end):
    """Only ordinary UTC weekly closures; unsupported calendars stay blocked."""
    # Holiday intervals add closures; they cannot open a weekly closed interval.
    # We do not certify extra holiday closures through this regular-session path.
    if metadata.get('scheduleTimeZone') != 'UTC' or metadata.get('tradingMode') != 'ENABLED':
        return False
    if scheduled_state(metadata, start) != 'SCHEDULED_CLOSED':
        return False
    week = start.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=(start.weekday()+1) % 7)
    if end > week + timedelta(days=7):
        return False
    return not any(start < week + timedelta(seconds=integer(row['endSecond']))
                   and week + timedelta(seconds=integer(row['startSecond'])) < end
                   for row in metadata['schedule'])


def validate(proof, account, symbols, now):
    body = {k: v for k, v in proof.items() if k != 'evidence_hash'}
    if digest(body) != proof.get('evidence_hash'):
        raise ValueError('closure evidence hash')
    symbol = proof['symbol']; audit = proof['audit']
    if (proof['account_id'] != str(account) or audit['account_id'] != str(account)
            or symbol not in symbols or str(symbols[symbol]) != audit['symbol_id']
            or str(proof['metadata']['symbolId']) != audit['symbol_id']):
        raise ValueError('foreign closure evidence')
    start, end, observed = utc(audit['start']), utc(audit['end']), utc(audit['observed_at'])
    metadata_at = utc(proof['metadata_observed_at'])
    expires = utc(proof['valid_until'])
    if (start.second or start.microsecond or end.second or end.microsecond
            or not timedelta(minutes=1) <= end-start <= timedelta(hours=1)
            or not start <= end <= observed <= now < expires
            or not end <= metadata_at <= observed
            or observed-start > timedelta(days=1)
            or expires > min(observed, metadata_at)+timedelta(days=1)):
        raise ValueError('stale or invalid closure interval')
    if (audit['status'] != 'NO_TICKS_REPORTED' or audit['bar_count'] != 0
            or audit['tick_counts'] != {'bid': 0, 'ask': 0}
            or audit['orders_enabled'] is not False or audit['repaired'] is not False
            or set(audit['response_hashes']) != {'bars', 'bid', 'ask'}
            or any(len(h) != 64 or any(c not in '0123456789abcdef' for c in h)
                   for h in audit['response_hashes'].values())):
        raise ValueError('complete empty history required')
    if not regular_closed(proof['metadata'], start, end):
        raise ValueError('interval not wholly within verified regular closure')
    return symbol, start, end


def certify(probe, symbol, now):
    if probe.get('status') != 'COLLECTED' or probe.get('mode') != 'demo-readonly' or probe.get('orders_enabled') is not False:
        raise ValueError('collected read-only probe required')
    account = probe['account_id']; sid = probe['symbols'][symbol]
    if str(probe['metadata']['ctidTraderAccountId']) != account:
        raise ValueError('foreign metadata')
    rows = [row for row in probe['metadata']['symbol'] if str(row['symbolId']) == str(sid)]
    if len(rows) != 1:
        raise ValueError('unique symbol metadata required')
    # Keep only relevant metadata; no balances, credentials or order facts.
    metadata = {k: rows[0][k] for k in ('symbolId', 'schedule', 'scheduleTimeZone', 'tradingMode', 'holiday') if k in rows[0]}
    observed = min(utc(probe['collected_at']), utc(probe['gap_audit']['observed_at']))
    body = dict(account_id=account, symbol=symbol, audit=probe['gap_audit'], metadata=metadata,
                metadata_observed_at=probe['collected_at'], valid_until=(observed+timedelta(days=1)).isoformat(),
                source_probe_hash=digest(probe))
    body['evidence_hash'] = digest(body)
    validate(body, account, probe['symbols'], now)
    return body


def intervals(config, account, now):
    proofs = config.get('verified_closures', [])
    if len(proofs) > 24:
        raise ValueError('closure evidence budget exceeded')
    result = [validate(p, account, config['symbols'], now) for p in proofs]
    if len(set(result)) != len(result):
        raise ValueError('duplicate closure evidence')
    for symbol, start, end in result:
        if any(symbol == s and (start, end) != (a, z) and start < z and a < end for s, a, z in result):
            raise ValueError('overlapping closure evidence')
    return result
