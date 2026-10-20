"""Reconcile reviewed public FxPro facts with private account metadata.

This review artifact is deliberately not a CapabilityReport or an order policy.
Matching published prices/fees does not establish execution or settlement behavior.
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from trading_platform.contracts.values import digest, utc
from .normalization import integer, units
from .sessions import scheduled_state

SOURCES = {
    'EURUSD': 'https://www.fxpro.com/trading/forex/eurusd',
    'XAUUSD': 'https://www.fxpro.com/trading/metals/gold',
    'commission': 'https://www.fxpro.com/commissions-swap-charges',
}
# Reviewed cTrader sections on 2026-10-20, not live scraped settings.
PUBLIC = {
    'EURUSD': {'minimum': '1000', 'step': '1000', 'lot': '100000', 'tick': None},
    'XAUUSD': {'minimum': '1', 'step': '100', 'lot': '100', 'tick': '0.01'},
}


def reconcile(probe, account, now):
    if (probe.get('status') != 'COLLECTED' or probe.get('mode') != 'demo-readonly'
            or probe.get('orders_enabled') is not False or probe.get('account_id') != str(account)):
        raise ValueError('collected bound read-only probe required')
    at = utc(probe['collected_at'])
    if not 0 <= (now - at).total_seconds() < 86400:
        raise ValueError('stale specification metadata')
    trader = probe['economics']['trader']
    if trader.get('brokerName') != 'FxPro' or str(trader.get('ctidTraderAccountId')) != str(account):
        raise ValueError('selected FxPro account required')
    if str(probe['metadata'].get('ctidTraderAccountId')) != str(account):
        raise ValueError('foreign symbol metadata')
    rows = probe['metadata']['symbol']
    metadata = {integer(row['symbolId']): row for row in rows}
    if len(rows) != len(metadata):
        raise ValueError('duplicate symbol metadata')
    result = {}
    for name, sid in probe['symbols'].items():
        if name not in PUBLIC:
            raise ValueError('unreviewed public symbol')
        raw = metadata[integer(sid)]
        public = PUBLIC[name]
        actual = {key: str(units(raw[field])) for key, field in
                  [('minimum', 'minVolume'), ('maximum', 'maxVolume'), ('step', 'stepVolume'), ('lot', 'lotSize')]}
        if Decimal(actual['maximum']) < Decimal(actual['minimum']):
            raise ValueError('invalid volume grid')
        comparisons = {key: {'public': public[key], 'account': actual[key],
                             'matches': Decimal(public[key]) == Decimal(actual[key])}
                       for key in ('minimum', 'step', 'lot')}
        rate = Decimal(integer(raw['preciseTradingCommissionRate'])) / Decimal('1e8')
        if rate < 0:
            raise ValueError('invalid commission rate')
        comparisons['commission_usd_per_million_per_side'] = {
            'public': '35', 'account': str(rate),
            'matches': raw['commissionType'] == 'USD_PER_MILLION_USD' and rate == 35}
        minimum_fee = Decimal(integer(raw['preciseMinCommission'])) / Decimal('1e8')
        if minimum_fee < 0:
            raise ValueError('invalid minimum commission')
        conflicts = sorted(key for key, value in comparisons.items() if not value['matches'])
        result[name] = {
            'symbol_id': str(sid), 'source': SOURCES[name], 'comparisons': comparisons,
            'conflicts': conflicts, 'normalized_grid': actual,
            'published_tick': public['tick'],
            'price_display_digits': integer(raw['digits']),
            'schedule_state_at_review': scheduled_state(raw, now),
            'minimum_commission': str(minimum_fee),
            'minimum_commission_type': raw['minCommissionType'],
            'minimum_commission_asset': raw.get('minCommissionAsset'),
            'pnl_conversion_fee_rate': raw.get('pnlConversionFeeRate'),
            'account_currency': probe['economics']['account']['currency'],
            'unresolved': ['tradable_tick_account_binding', 'complete_cost_rounding_and_settlement',
                           'current_session', 'limit_gtd_protection_acceptance'],
        }
    body = dict(format=1, account_id=str(account), observed_at=at.isoformat(),
                valid_until=(at + timedelta(days=1)).isoformat(), reviewed_at=now.isoformat(),
                public_review_date='2026-10-20', sources=SOURCES, symbols=result,
                input_hash=digest(probe), orders_enabled=False, qualification_complete=False)
    body['evidence_hash'] = digest(body)
    return body


def main():
    parser = argparse.ArgumentParser()
    for name in ('probe', 'account', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = reconcile(json.loads(Path(args.probe).read_text()), args.account, datetime.now(timezone.utc))
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(result, output, sort_keys=True)
        output.write('\n')
    print(json.dumps({'report_written': True, 'orders_enabled': False,
                      'conflicts': {name: row['conflicts'] for name, row in result['symbols'].items()}}))


if __name__ == '__main__':
    main()
