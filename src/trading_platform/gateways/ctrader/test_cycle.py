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
        # Immutable archives and consumption tombstones stay on disk. They
        # must not be decoded into every active-cycle transition.
        rows={r['id']:json.loads(r['body']) for r in c.execute(
            "SELECT id,body FROM checkpoints WHERE id NOT GLOB 'completed-test:*' "
            "AND id NOT GLOB 'consumed-test:*' AND id NOT GLOB 'consumed-approval:*'")}
        used_next=c.execute('SELECT 1 FROM checkpoints WHERE id=?',
                            ('consumed-test:'+account+':'+next_test_id,)).fetchone()
        attempt=rows.get('attended-attempt:'+account);monitor=rows.get('attended-monitor:'+account)
        if (not attempt or not monitor or monitor.get('status')!='COMPLETE' or not monitor.get('completed_once')
                or monitor['approval_hash']!=attempt['approval_hash'] or next_test_id==attempt['owner']
                or used_next):
            raise ValueError('completed prior cycle and unused next identity required')
        sends={k:v for k,v in rows.items() if k.startswith('gateway-send:')}
        if set(sends)!={'gateway-send:'+attempt['command_id']}:
            raise ValueError('unresolved or foreign entry history')
        send=next(iter(sends.values()))
        if send['instance']!=attempt['owner'] or str(send['fields']['ctidTraderAccountId'])!=account or send['status']!='OBSERVED':
            raise ValueError('prior entry scope unresolved')
        raw=rows.get('provider-settlement:'+attempt['command_id'])
        unfilled=rows.get('provider-unfilled:'+attempt['command_id'])
        positions={k:v for k,v in rows.items() if k.startswith('broker-position:')}
        if raw is not None and unfilled is None:
            settlement=Settlement.model_validate_json(canonical(raw));pid=settlement.position_id
            if set(positions)!={'broker-position:'+pid}:raise ValueError('unexpected prior positions')
            position=positions['broker-position:'+pid]
            if (not position['closed'] or Decimal(position['quantity'])!=0 or position['owner']!=attempt['owner']
                    or settlement.command_id!=attempt['command_id']):raise ValueError('owned settled closure required')
        elif unfilled is not None and raw is None:
            from .unfilled import UnfilledCertificate
            proof=UnfilledCertificate.model_validate_json(canonical(unfilled))
            order=rows.get('broker-order:'+proof.order_id)
            if (proof.account_id!=account or proof.command_id!=attempt['command_id'] or proof.owner!=attempt['owner']
                    or not order or not order['terminal'] or digest(order['record'])!=proof.order_hash
                    or proof.order_id!=send.get('broker_order_id')):raise ValueError('unfilled prior review mismatch')
            pid=str(order['record'].get('positionId',''))
            if any(k!='broker-position:'+pid or Decimal(p['quantity'])!=0 or p['record'].get('positionStatus')!='POSITION_STATUS_CREATED' for k,p in positions.items()):
                raise ValueError('unexpected unfilled position')
        else:raise ValueError('exactly one prior completion review required')
        for key,value in rows.items():
            if key.startswith('broker-order:') and (not value['terminal'] or str(value['record'].get('positionId',''))!=pid):
                raise ValueError('nonterminal or foreign order history')
            if key.startswith('gateway-management:') and (value['status']!='TARGET_RESOLVED' or value['owner']!=attempt['owner']):
                raise ValueError('unresolved cleanup')
            if key.startswith(('provider-settlement:','provider-unfilled:')) and key not in ('provider-settlement:'+attempt['command_id'],'provider-unfilled:'+attempt['command_id']):
                raise ValueError('unexpected settlement')
        halts=[dict(r) for r in c.execute('SELECT id,reason FROM halts')]
        if any(h['id']!='protection:'+pid or h['reason']!='UNCONFIRMED_BROKER_PROTECTION' for h in halts):
            raise ValueError('unresolved unrelated halt')
        prefixes=('attended-attempt:','attended-monitor:','gateway-send:','gateway-management:',
                  'broker-position:','broker-order:','broker-deal:','execution:','provider-settlement:','provider-unfilled:')
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
