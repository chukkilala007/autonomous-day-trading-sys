"""Bind operator-captured Algo metadata to Open API identity; no promotion."""
import argparse
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field
from trading_platform.contracts.values import Record, Positive, Time, digest, utc
from .normalization import integer, units


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


def challenge(probe, account, now):
    return dict(format=1, account_id=str(account), broker_login=identity(probe, account, now),
                probe_hash=digest(probe), nonce=secrets.token_hex(16),
                created_at=now.isoformat(), valid_until=(now + timedelta(hours=1)).isoformat())


def review(raw, request, probe, account, now):
    capture = Capture.model_validate_json(json.dumps(raw))
    login = identity(probe, account, now)
    if (request.get('format') != 1 or request.get('account_id') != str(account)
            or request.get('probe_hash') != digest(probe) or request.get('broker_login') != login
            or request.get('nonce') != capture.nonce or capture.broker_login != login):
        raise ValueError('capture/challenge identity mismatch')
    created, expiry = utc(request['created_at']), utc(request['valid_until'])
    if not (created <= capture.observed_at <= now < expiry <= created + timedelta(hours=1)):
        raise ValueError('capture outside challenge window')
    if (now - capture.observed_at).total_seconds() > 300:
        raise ValueError('stale Algo capture')
    sid = integer(probe['symbols']['EURUSD'])
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
    return dict(account_id=str(account), symbol='EURUSD', observed_at=capture.observed_at.isoformat(),
                tick_size=str(capture.tick_size), capture_hash=digest(raw), probe_hash=digest(probe),
                challenge_hash=digest(request), classification='operator_capture_pending_review',
                identity_checks_passed=True, orders_enabled=False, qualification_complete=False,
                limitation='Local JSON is not broker-signed evidence. Verify capture provenance before policy promotion; '
                           'entry/protection grid applicability and execution behavior remain separate.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['challenge', 'review'])
    for name in ('probe', 'account', 'output'): p.add_argument('--' + name, required=True)
    p.add_argument('--challenge'); p.add_argument('--capture')
    a = p.parse_args(); now = datetime.now(timezone.utc)
    probe = json.loads(Path(a.probe).read_text())
    if a.mode == 'challenge': result = challenge(probe, a.account, now)
    else:
        if not a.challenge or not a.capture: p.error('review requires --challenge and --capture')
        result = review(json.loads(Path(a.capture).read_text()), json.loads(Path(a.challenge).read_text()), probe, a.account, now)
    fd = os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out: json.dump(result, out, sort_keys=True); out.write('\n')
    print(json.dumps({'report_written': True, 'orders_enabled': False}))


if __name__ == '__main__': main()
