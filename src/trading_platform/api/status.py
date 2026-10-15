import json
from datetime import datetime,timezone
from trading_platform.contracts.values import utc


def status(db,now=None):
    now=now or datetime.now(timezone.utc)
    with db.mutex:
        c=db.connection
        latest=c.execute('SELECT body FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        event=json.loads(latest['body']) if latest else None
        lag=None if event is None else max(0,(now-utc(event['available_at'])).total_seconds())
        metadata=c.execute("SELECT body FROM checkpoints WHERE id='operations:identity'").fetchone()
        identity=json.loads(metadata['body']) if metadata else {'mode':'unknown','account_alias':'unknown'}
        risk=[dict(r) for r in c.execute("SELECT * FROM reservations WHERE status!='RELEASED'")]
        decisions=[]
        for row in c.execute('SELECT id,body FROM decisions ORDER BY event_seq DESC LIMIT 100'):
            body=json.loads(row['body'])
            decisions.append({k:body.get(k) for k in ('instance','outcome','at','event_id','snapshot_hash','reasons','package','config_hash')}|{'id':row['id']})
        return dict(identity=identity,observed_at=now.isoformat(),data_age_seconds=lag,stale=lag is None or lag>30,
            instances=[dict(r) for r in c.execute('SELECT id,package,cursor,status,halt FROM instances')],
            orders=[dict(r) for r in c.execute('SELECT id,instance,instrument,status,revision FROM commands')],
            positions=[json.loads(r['body']) for r in c.execute('SELECT body FROM positions')],risk=risk,
            limits=[json.loads(r['body']) for r in c.execute("SELECT body FROM checkpoints WHERE id LIKE 'risk:%'")],
            halts=[dict(r) for r in c.execute('SELECT * FROM halts')],decisions=decisions,
            executions=[json.loads(r['body']) for r in c.execute('SELECT body FROM broker_events ORDER BY rowid DESC LIMIT 100')])
