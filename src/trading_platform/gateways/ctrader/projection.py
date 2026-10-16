"""Project authoritative owned broker records into shared execution events.

Settlement values must be supplied by an audited account-currency cost adapter.
Missing facts retain reservations; no price-touch or paper P&L fallback exists.
"""
import json
from decimal import Decimal as D
from datetime import datetime,timezone
from trading_platform.contracts.values import canonical,digest
from trading_platform.execution.state_machine import BrokerEvent
from trading_platform.execution.recovery import matches


class Projection:
    def __init__(self,db): self.db=db

    def read(self,key):
        row=self.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()
        return json.loads(row['body']) if row else None

    def refresh(self,settlements=None):
        blockers=[]
        for row in self.db.connection.execute("SELECT id,body FROM checkpoints WHERE id LIKE 'gateway-send:%'").fetchall():
            send=json.loads(row['body']);command=row['id'].split(':',1)[1]
            order=self.read('broker-order:'+str(send.get('broker_order_id','')))
            if not order or order['owner']!=send['instance'] or not matches(send['fields'],order['record']):
                blockers.append('ORDER_RECONCILIATION:'+command);continue
            raw=order['record'];pid=raw.get('positionId')
            position=self.read('broker-position:'+str(pid)) if pid else None
            filled=D(str(raw.get('executedVolume',0)))/100
            prior=self.read('projection:'+command)
            if prior: filled=max(filled,D(prior['filled']))
            if filled and (not position or position['owner']!=send['instance']):
                blockers.append('POSITION_RECONCILIATION:'+command);continue
            kinds={'ORDER_STATUS_ACCEPTED':'PART_FILLED' if filled else 'ACCEPTED','ORDER_STATUS_FILLED':'FILLED',
                   'ORDER_STATUS_CANCELLED':'CANCELLED','ORDER_STATUS_EXPIRED':'EXPIRED','ORDER_STATUS_REJECTED':'REJECTED'}
            kind=kinds.get(raw.get('orderStatus'))
            if kind is None: blockers.append('UNKNOWN_ORDER_STATUS:'+command);continue
            price=position['record'].get('price') if filled else None
            if filled and price is None: blockers.append('FILL_PRICE_REQUIRED:'+command);continue
            net=None
            if filled and position['closed']:
                settlement=(settlements or {}).get(command)
                if not settlement or settlement.get('position_id')!=str(pid) or not settlement.get('complete') or not settlement.get('evidence_hash'):
                    blockers.append('SETTLEMENT_REQUIRED:'+command);continue
                net=D(settlement['net'])
                if not net.is_finite(): raise ValueError('nonfinite settlement')
                kind='CLOSED'
            quantity=D(position['quantity']) if filled and not position['closed'] else D(0)
            if filled and quantity>filled: raise ValueError('position exceeds owned entry; reconciliation required')
            if kind=='FILLED' and prior and quantity>0 and (quantity<D(prior.get('open_quantity') or '0') or prior['kind']=='REDUCED'): kind='REDUCED'
            timestamp=max(order['updated'],position['updated'] if position else 0)
            facts=dict(command=command,kind=kind,at=datetime.fromtimestamp(timestamp/1000,timezone.utc),filled=filled,
                       average_price=price,protected=bool(position and position['protected']) if filled else True,
                       stop=position['record'].get('stopLoss') if position else None,open_quantity=quantity,net=net)
            fingerprint=digest(facts)
            if prior and prior['fingerprint']==fingerprint: continue
            revision=prior['revision']+1 if prior else 1
            event=BrokerEvent(id=digest((command,revision,fingerprint)),revision=revision,**facts)
            with self.db.transaction() as c:
                c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('projection:'+command,canonical(dict(json.loads(event.model_dump_json()),fingerprint=fingerprint))))
                c.execute('INSERT INTO checkpoints VALUES (?,?)',('projected-event:'+event.id,canonical(event)))
        return blockers

    def events(self):
        return [BrokerEvent.model_validate_json(r['body']) for r in self.db.connection.execute("SELECT body FROM checkpoints WHERE id LIKE 'projected-event:%' ORDER BY rowid")]
