"""Bind operator-captured Algo metadata to Open API identity; no promotion."""
import argparse
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field
from trading_platform.contracts.values import Record, Name, Positive, Time, digest, utc
from .normalization import integer, units
from .broker_profile import CaptureScope, Label, Hash, demo_identity


class Capture(Record):
    format: Literal[1]
    source: Literal['ctrader_algo_contract_exporter_v1']
    nonce: str = Field(pattern=r'^[0-9a-f]{32}$')
    observed_at: Time
    is_live: Literal[False]
    running_mode: Literal['RealTime']
    broker_login: str = Field(pattern=r'^[0-9]+$')
    broker: Literal['FxPro']
    currency: Literal['USD']
    symbol: Literal['EURUSD']
    tick_size: Positive
    pip_size: Positive
    lot_size: Positive
    minimum: Positive
    maximum: Positive
    step: Positive


class CaptureV2(Capture):
    format: Literal[2]
    source: Literal['ctrader_algo_contract_exporter_v2']
    symbol: Literal['EURUSD', '#USNDAQ100']
    quote_currency: Literal['USD']
    tick_value: Positive
    pip_value: Positive


class CaptureV3(CaptureV2):
    format: Literal[3]
    source: Literal['ctrader_algo_contract_exporter_v3']
    broker: Label
    currency: Name
    symbol: Name
    quote_currency: Name
    scope_hash: Hash


def scope_identity(probe, account, now, scope, pin):
    if (probe.get('status')!='COLLECTED' or probe.get('mode')!='demo-readonly'
            or probe.get('orders_enabled') is not False or probe.get('account_id')!=str(account)
            or not 0 <= (now-utc(probe['collected_at'])).total_seconds() < 86400
            or str(probe['metadata'].get('ctidTraderAccountId'))!=str(account)):
        raise ValueError('bound current demo probe required')
    actual=demo_identity(probe['economics'],account=account,binding=probe.get('demo_binding'),
                         generation=probe['generation'])
    scope=scope.verify(actual,pin,now)
    if integer(probe['symbols'][scope.native_symbol])!=scope.symbol_id:
        raise ValueError('capture scope symbol mismatch')
    login=integer(probe['economics']['trader']['traderLogin'])
    if login<=0: raise ValueError('broker login required')
    return scope,str(login)


def identity(probe, account, now):
    if (probe.get('status') != 'COLLECTED' or probe.get('mode') != 'demo-readonly'
            or probe.get('orders_enabled') is not False or probe.get('account_id') != str(account)):
        raise ValueError('bound read-only probe required')
    if not 0 <= (now - utc(probe['collected_at'])).total_seconds() < 86400:
        raise ValueError('stale probe')
    trader = probe['economics']['trader']
    if (str(trader.get('ctidTraderAccountId')) != str(account) or trader.get('brokerName') != 'FxPro'
            or probe['economics']['account']['currency'] != 'USD'
            or str(probe['metadata'].get('ctidTraderAccountId')) != str(account)):
        raise ValueError('foreign account metadata')
    login = integer(trader['traderLogin'])
    if login <= 0:
        raise ValueError('broker login required; Open API account ID is not Algo Account.Number')
    return str(login)


def challenge(probe, account, now, symbol='EURUSD', *, scope=None, approved_scope_hash=None):
    if scope is not None:
        scope,login=scope_identity(probe,account,now,scope,approved_scope_hash)
        if symbol!=scope.native_symbol: raise ValueError('capture scope symbol mismatch')
        return dict(format=2,symbol=symbol,account_id=str(account),broker_login=login,
                    broker=scope.identity.broker,currency=scope.identity.currency,
                    quote_currency=scope.quote_currency,scope_hash=digest(scope),
                    probe_hash=digest(probe),nonce=secrets.token_hex(16),created_at=now.isoformat(),
                    valid_until=min(now+timedelta(hours=1),scope.valid_until).isoformat())
    if approved_scope_hash is not None: raise ValueError('capture scope required')
    if symbol not in ('EURUSD', '#USNDAQ100') or symbol not in probe.get('symbols', {}):
        raise ValueError('explicit supported probe symbol required')
    return dict(format=1, symbol=symbol, account_id=str(account), broker_login=identity(probe, account, now),
                probe_hash=digest(probe), nonce=secrets.token_hex(16),
                created_at=now.isoformat(), valid_until=(now + timedelta(hours=1)).isoformat())


def review(raw, request, probe, account, now, *, scope=None, approved_scope_hash=None):
    kind={1:Capture,2:CaptureV2,3:CaptureV3}.get(raw.get('format'))
    if kind is None: raise ValueError('unsupported capture version')
    capture=kind.model_validate_json(json.dumps(raw))
    modern=isinstance(capture,CaptureV3)
    if modern:
        if scope is None: raise ValueError('pinned capture scope required')
        scope,login=scope_identity(probe,account,now,scope,approved_scope_hash)
        if (capture.scope_hash!=digest(scope) or request.get('scope_hash')!=digest(scope)
                or capture.broker!=scope.identity.broker or capture.currency!=scope.identity.currency
                or capture.quote_currency!=scope.quote_currency or capture.symbol!=scope.native_symbol
                or any(request.get(k)!=getattr(capture,k) for k in ('broker','currency','quote_currency'))):
            raise ValueError('capture scope mismatch')
    elif scope is not None or approved_scope_hash is not None:
        raise ValueError('legacy capture cannot acquire profile provenance')
    if capture.symbol != request.get('symbol', 'EURUSD') or (capture.format == 2 and 'symbol' not in request):
        raise ValueError('capture/challenge symbol mismatch')
    if not modern: login = identity(probe, account, now)
    if (request.get('format') != (2 if modern else 1) or request.get('account_id') != str(account)
            or request.get('probe_hash') != digest(probe) or request.get('broker_login') != login
            or request.get('nonce') != capture.nonce or capture.broker_login != login):
        raise ValueError('capture/challenge identity mismatch')
    created, expiry = utc(request['created_at']), utc(request['valid_until'])
    if not (created <= capture.observed_at <= now < expiry <= created + timedelta(hours=1)):
        raise ValueError('capture outside challenge window')
    if (now - capture.observed_at).total_seconds() > 300:
        raise ValueError('stale Algo capture')
    sid = integer(probe['symbols'][capture.symbol])
    rows = probe['metadata']['symbol']
    ids = [integer(r['symbolId']) for r in rows]
    if len(set(ids)) != len(ids) or ids.count(sid) != 1:
        raise ValueError('ambiguous symbol binding')
    row = rows[ids.index(sid)]
    for field, wire in [('lot_size', 'lotSize'), ('minimum', 'minVolume'),
                        ('maximum', 'maxVolume'), ('step', 'stepVolume')]:
        if getattr(capture, field) != units(row[wire]):
            raise ValueError('Algo/Open API contract mismatch: ' + field)
    from decimal import Decimal
    if capture.pip_size != Decimal(10) ** -integer(row['pipPosition']):
        raise ValueError('pip mismatch')
    if capture.tick_size > capture.pip_size or capture.pip_size % capture.tick_size:
        raise ValueError('inconsistent tick/pip geometry')
    result = dict(account_id=str(account), symbol=capture.symbol, observed_at=capture.observed_at.isoformat(),
                tick_size=str(capture.tick_size), capture_hash=digest(raw), probe_hash=digest(probe),
                challenge_hash=digest(request), classification='operator_capture_pending_review',
                identity_checks_passed=True, orders_enabled=False, qualification_complete=False,
                limitation='Local JSON is not broker-signed evidence. Verify capture provenance before policy promotion; '
                           'entry/protection grid applicability and execution behavior remain separate.')
    if isinstance(capture, CaptureV2):
        result.update(tick_value=str(capture.tick_value), pip_value=str(capture.pip_value),
                      quote_currency=capture.quote_currency,
                      candidate_value_per_unit_per_price=str(capture.tick_value/capture.tick_size),
                      monetary_value_classification='startup_snapshot_pending_review')
    if modern: result.update(scope_hash=digest(scope),instrument=scope.instrument,
                             monetary_value_currency=capture.currency)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['challenge', 'review'])
    for name in ('probe', 'account', 'output'): p.add_argument('--' + name, required=True)
    p.add_argument('--challenge'); p.add_argument('--capture')
    p.add_argument('--symbol', default='EURUSD')
    p.add_argument('--scope'); p.add_argument('--approved-scope-hash')
    a = p.parse_args(); now = datetime.now(timezone.utc)
    probe = json.loads(Path(a.probe).read_text())
    scope=CaptureScope.model_validate_json(Path(a.scope).read_text()) if a.scope else None
    kw=dict(scope=scope,approved_scope_hash=a.approved_scope_hash)
    if a.mode == 'challenge': result = challenge(probe, a.account, now, a.symbol, **kw)
    else:
        if not a.challenge or not a.capture: p.error('review requires --challenge and --capture')
        result = review(json.loads(Path(a.capture).read_text()), json.loads(Path(a.challenge).read_text()), probe, a.account, now, **kw)
    fd = os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out: json.dump(result, out, sort_keys=True); out.write('\n')
    print(json.dumps({'report_written': True, 'orders_enabled': False}))


if __name__ == '__main__': main()
