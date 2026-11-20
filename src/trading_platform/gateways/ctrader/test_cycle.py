"""Explicit audited transition between completed attended demo test cycles."""
import json
from decimal import Decimal
from trading_platform.contracts.values import canonical,digest,utc
from .valuation import Settlement


def advance_completed_test(db, account, next_test_id, economics, now):
    account=str(account)
    if not isinstance(next_test_id,str) or not next_test_id or any(c.isspace() for c in next_test_id):
        raise ValueError('explicit next test identity required')
    if (economics.get('account_id')!=account or not 0<=(now-utc(economics['observed_at'])).total_seconds()<2
            or str(economics['reconciliation'].get('ctidTraderAccountId'))!=account
            or economics['reconciliation'].get('order') or economics['reconciliation'].get('position')):
        raise ValueError('fresh flat account reconciliation required')
    with db.transaction() as c:
        for table in ('commands','attempts','positions','reservations'):
            if c.execute('SELECT 1 FROM '+table+' LIMIT 1').fetchone():
                raise ValueError('core lifecycle still active')
        rows={r['id']:json.loads(r['body']) for r in c.execute('SELECT id,body FROM checkpoints')}
        attempt=rows.get('attended-attempt:'+account);monitor=rows.get('attended-monitor:'+account)
        if (not attempt or not monitor or monitor.get('status')!='COMPLETE' or not monitor.get('completed_once')
                or monitor['approval_hash']!=attempt['approval_hash'] or next_test_id==attempt['owner']
                or 'consumed-test:'+account+':'+next_test_id in rows):
            raise ValueError('completed prior cycle and unused next identity required')
        sends={k:v for k,v in rows.items() if k.startswith('gateway-send:')}
        if set(sends)!={'gateway-send:'+attempt['command_id']}:
            raise ValueError('unresolved or foreign entry history')
        send=next(iter(sends.values()))
        if send['instance']!=attempt['owner'] or str(send['fields']['ctidTraderAccountId'])!=account or send['status']!='OBSERVED':
            raise ValueError('prior entry scope unresolved')
        raw=rows.get('provider-settlement:'+attempt['command_id'])
        if raw is None:raise ValueError('prior settlement required')
        settlement=Settlement.model_validate_json(canonical(raw));pid=settlement.position_id
        positions={k:v for k,v in rows.items() if k.startswith('broker-position:')}
        if set(positions)!={'broker-position:'+pid}:raise ValueError('unexpected prior positions')
        position=positions['broker-position:'+pid]
        if (not position['closed'] or Decimal(position['quantity'])!=0 or position['owner']!=attempt['owner']
                or settlement.command_id!=attempt['command_id']):raise ValueError('owned settled closure required')
        for key,value in rows.items():
            if key.startswith('broker-order:') and (not value['terminal'] or str(value['record'].get('positionId'))!=pid):
                raise ValueError('nonterminal or foreign order history')
            if key.startswith('gateway-management:') and (value['status']!='TARGET_RESOLVED' or value['owner']!=attempt['owner']):
                raise ValueError('unresolved cleanup')
            if key.startswith('provider-settlement:') and key!='provider-settlement:'+attempt['command_id']:
                raise ValueError('unexpected settlement')
        halts=[dict(r) for r in c.execute('SELECT id,reason FROM halts')]
        if any(h['id']!='protection:'+pid or h['reason']!='UNCONFIRMED_BROKER_PROTECTION' for h in halts):
            raise ValueError('unresolved unrelated halt')
        prefixes=('attended-attempt:','attended-monitor:','gateway-send:','gateway-management:',
                  'broker-position:','broker-order:','broker-deal:','execution:','provider-settlement:')
        archived={k:v for k,v in rows.items() if k.startswith(prefixes)}
        if any(k.startswith(('attended-attempt:','attended-monitor:')) and k not in ('attended-attempt:'+account,'attended-monitor:'+account) for k in archived):
            raise ValueError('foreign account cycle')
        archive=dict(account_id=account,test_id=attempt['owner'],next_test_id=next_test_id,at=now,
                     economics_hash=digest(economics),checkpoints=archived,resolved_halts=halts)
        key='completed-test:'+account+':'+attempt['owner']
        c.execute('INSERT INTO checkpoints VALUES (?,?)',(key,canonical(archive)))
        for prefix,value in [('consumed-approval:',attempt['approval_hash']),('consumed-test:',attempt['owner'])]:
            c.execute('INSERT INTO checkpoints VALUES (?,?)',(prefix+account+':'+value,canonical(dict(archive_hash=digest(archive)))))
        fence=rows.get('gateway-fence:'+account)
        if fence:
            c.execute('UPDATE checkpoints SET body=? WHERE id=?',(canonical(dict(core='test-cycle-transition',epoch=fence['epoch']+1)),'gateway-fence:'+account))
        for key in archived:c.execute('DELETE FROM checkpoints WHERE id=?',(key,))
        for halt in halts:c.execute('DELETE FROM halts WHERE id=?',(halt['id'],))
        c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('active-test-cycle:'+account,
                  canonical(dict(test_id=next_test_id,previous_archive_hash=digest(archive)))))
        return dict(status='NEXT_CYCLE_PREPARED',archive_hash=digest(archive),next_test_id=next_test_id)
