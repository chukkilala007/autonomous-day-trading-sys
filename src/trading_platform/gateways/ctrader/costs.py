"""Offline prospective cost arithmetic. Never certifies an executable Contract.

Precise protocol fields only; conversion paths and fee incidence require audit.
"""
from decimal import Decimal


def number(value, *, positive=False):
    if isinstance(value, (float, bool)):
        raise ValueError('exact decimal required')
    result = Decimal(value)
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError('invalid nonnegative amount')
    return result


def conversion(amount, source, target, quotes, *, account, now):
    """Upper cost conversion over an explicit ordered path, not a mid-price."""
    result = number(amount)
    currency = source
    seen = {currency}
    for quote in quotes:
        if quote['account'] != account or not 0 <= (now-quote['observed_at']).total_seconds() <= 2:
            raise ValueError('foreign or stale conversion')
        bid, ask = number(quote['bid'], positive=True), number(quote['ask'], positive=True)
        if bid > ask:
            raise ValueError('crossed conversion quote')
        if currency == quote['base']:
            currency = quote['quote']; result *= ask
        elif currency == quote['quote']:
            currency = quote['base']; result /= bid
        else:
            raise ValueError('disconnected conversion path')
        if currency in seen:
            raise ValueError('cyclic conversion path')
        seen.add(currency)
    if currency != target:
        raise ValueError('incomplete conversion path')
    return result


def commission(metadata, *, quantity, price, quote_currency, account_currency,
               account, now, paths):
    """One charge incidence, converted to account currency before applying minimum.

Caller must audit quantity as underlying units and supply the complete FX paths.
No round-trip, partial-fill, swap or P&L conversion-fee assumption is made.
"""
    quantity, price = number(quantity, positive=True), number(price, positive=True)
    raw_rate = number(metadata['preciseTradingCommissionRate'])
    kind = metadata['commissionType']
    def convert(value, source, target):
        return conversion(value, source, target, () if source == target else paths[(source, target)], account=account, now=now)
    if kind == 'USD_PER_MILLION_USD':
        charge = convert(quantity * price, quote_currency, 'USD') * raw_rate / Decimal('1e14')
        currency = 'USD'
    elif kind in ('USD_PER_LOT', 'QUOTE_CCY_PER_LOT'):
        lot = number(metadata['lotSize'], positive=True) / 100
        charge = quantity / lot * raw_rate / Decimal('1e8')
        currency = 'USD' if kind == 'USD_PER_LOT' else quote_currency
    elif kind == 'PERCENTAGE_OF_VALUE':
        charge = quantity * price * raw_rate / Decimal('1e7')
        currency = quote_currency
    else:
        raise ValueError('unsupported commission type')
    minimum = number(metadata['preciseMinCommission']) / Decimal('1e8')
    minimum_type = metadata['minCommissionType']
    if minimum_type not in ('CURRENCY', 'QUOTE_CURRENCY'):
        raise ValueError('unsupported minimum type')
    minimum_currency = metadata['minCommissionAsset'] if minimum_type == 'CURRENCY' else quote_currency
    return max(convert(charge, currency, account_currency), convert(minimum, minimum_currency, account_currency))


def expected_margin(response, *, request, account, symbol_id, volume, side, observed_at, now):
    """Map only the exact correlated request volume; never extrapolate tiers."""
    if side not in ('BUY', 'SELL') or type(volume) is not int or volume <= 0:
        raise ValueError('invalid margin quantity or side')
    if request['ctidTraderAccountId'] != account or response['ctidTraderAccountId'] != account or request['symbolId'] != symbol_id:
        raise ValueError('margin identity mismatch')
    if not 0 <= (now-observed_at).total_seconds() <= 2:
        raise ValueError('stale margin')
    volumes = request['volume']
    rows = response['margin']
    if len(set(volumes)) != len(volumes) or volume not in volumes or sorted(row['volume'] for row in rows) != sorted(volumes):
        raise ValueError('incomplete or duplicate margin volumes')
    digits = response['moneyDigits']
    if type(digits) is not int or not 0 <= digits <= 10:
        raise ValueError('invalid money scale')
    row = next(row for row in rows if row['volume'] == volume)
    return number(row['buyMargin' if side == 'BUY' else 'sellMargin']) / Decimal(10) ** digits
