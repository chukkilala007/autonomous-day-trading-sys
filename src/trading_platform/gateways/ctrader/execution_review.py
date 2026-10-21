"""Read-only preparation evidence, never an executable capability or policy."""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_platform.contracts.values import digest, utc
from .normalization import integer

SOURCES = {
    'request': 'https://help.ctrader.com/open-api/messages/#protooaneworderreq',
    'symbol': 'https://help.ctrader.com/open-api/model-messages/#protooasymbol',
    'trigger': 'https://help.ctrader.com/open-api/model-messages/#protooaordertriggermethod',
}
ACCOUNT_FIELDS = ('accountType', 'accessRights', 'isLimitedRisk')
SYMBOL_FIELDS = ('tradingMode', 'slDistance', 'tpDistance', 'distanceSetIn',
                 'guaranteedStopLoss', 'digits')


def protocol_profile():
    """Inspect the installed SDK; no client/session is constructed."""
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOANewOrderReq
    descriptor = ProtoOANewOrderReq.DESCRIPTOR
    expected = {'ctidTraderAccountId': 3, 'symbolId': 3, 'volume': 3,
                'orderType': 14, 'tradeSide': 14, 'timeInForce': 14,
                'expirationTimestamp': 3, 'limitPrice': 1, 'stopLoss': 1,
                'takeProfit': 1, 'clientOrderId': 9}
    fields = descriptor.fields_by_name
    issues = [name for name, kind in expected.items()
              if name not in fields or fields[name].type != kind]
    enums = {}
    for field, name, number in [('orderType', 'LIMIT', 2), ('timeInForce', 'GOOD_TILL_DATE', 1),
                                ('tradeSide', 'BUY', 1), ('tradeSide', 'SELL', 2)]:
        entry = fields.get(field)
        value = entry.enum_type.values_by_name.get(name) if entry and entry.enum_type else None
        enums[name] = value.number if value else None
        if enums[name] != number:
            issues.append(field + ':' + name)
    return {'classification': 'protocol_only', 'profile': 'absolute_protected_limit_gtd',
            'sdk_mapping_matches_transport': not issues, 'issues': sorted(issues),
            'enums': enums, 'descriptor_hash': digest(descriptor.file.serialized_pb.hex()),
            'stop_trigger_method_scope': 'pending STOP/STOP_LIMIT, not attached LIMIT protection',
            'broker_acceptance_observed': False}


def review(probe, account, symbol, now):
    if (probe.get('status') != 'COLLECTED' or probe.get('mode') != 'demo-readonly'
            or probe.get('orders_enabled') is not False or probe.get('account_id') != str(account)):
        raise ValueError('bound collected read-only probe required')
    at = utc(probe['collected_at'])
    if not 0 <= (now - at).total_seconds() < 86400:
        raise ValueError('stale profile evidence')
    trader = probe['economics']['trader']
    metadata = probe['metadata']
    if any(str(row.get('ctidTraderAccountId')) != str(account) for row in (trader, metadata)):
        raise ValueError('foreign profile evidence')
    sid = integer(probe['symbols'][symbol])
    rows = metadata['symbol']
    ids = [integer(row['symbolId']) for row in rows]
    if len(ids) != len(set(ids)) or ids.count(sid) != 1:
        raise ValueError('unique selected symbol metadata required')
    raw = rows[ids.index(sid)]
    restrictions = []
    for field, expected in [('accountType', 'HEDGED'), ('accessRights', 'FULL_ACCESS'),
                             ('isLimitedRisk', False)]:
        if field not in trader:
            restrictions.append('missing_account_' + field)
        elif type(trader[field]) is not type(expected) or trader[field] != expected:
            restrictions.append('unsupported_account_' + field)
    if raw.get('tradingMode') != 'ENABLED':
        restrictions.append('symbol_not_explicitly_enabled')
    for field in ('slDistance', 'tpDistance'):
        if field not in raw:
            restrictions.append('missing_' + field)
        elif integer(raw[field]) < 0:
            raise ValueError('negative protection distance')
    if raw.get('distanceSetIn') not in ('SYMBOL_DISTANCE_IN_POINTS', 'SYMBOL_DISTANCE_IN_PERCENTAGE'):
        restrictions.append('unknown_distance_unit')
    protocol = protocol_profile()
    if not protocol['sdk_mapping_matches_transport']:
        restrictions.append('sdk_profile_mismatch')
    body = {'format': 1, 'account_id': str(account), 'symbol': symbol, 'symbol_id': str(sid),
            'observed_at': at.isoformat(), 'reviewed_at': now.isoformat(),
            'valid_until': (at + timedelta(days=1)).isoformat(),
            'sources': SOURCES, 'protocol': protocol,
            'account_observations': {key: trader.get(key) for key in ACCOUNT_FIELDS},
            'symbol_observations': {key: raw.get(key) for key in SYMBOL_FIELDS},
            'profile_restrictions': sorted(restrictions),
            'remaining': ['account_bound_tradable_tick', 'complete_cost_rounding_settlement',
                          'fresh_proposal_margin_and_exposure', 'current_executable_session',
                          'attached_protection_trigger_and_acceptance', 'limit_gtd_broker_acceptance',
                          'bounded_test_controller_and_preview', 'explicit_submission_authorization'],
            'input_hash': digest(probe), 'orders_enabled': False, 'qualification_complete': False,
            'note': 'Metadata review only; no quote, executable session, authorization or capability promotion. '
                    'Absent optional fields remain unknown; display digits are not a tradable tick.'}
    body['evidence_hash'] = digest(body)
    return body


def main():
    parser = argparse.ArgumentParser()
    for name in ('probe', 'account', 'symbol', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = review(json.loads(Path(args.probe).read_text()), args.account, args.symbol,
                    datetime.now(timezone.utc))
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(result, output, sort_keys=True)
        output.write('\n')
    print(json.dumps({'report_written': True, 'orders_enabled': False,
                      'profile_restrictions': result['profile_restrictions'],
                      'remaining': result['remaining']}))


if __name__ == '__main__':
    main()
