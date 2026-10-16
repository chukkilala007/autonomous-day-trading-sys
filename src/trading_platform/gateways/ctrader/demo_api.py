"""Fenced demo protocol controller, exercised offline by deterministic transports.

Provider valuations and settlements are explicit audited inputs. Their absence
blocks entries; this controller never substitutes simulator economics.
"""
import json
from decimal import Decimal
from twisted.internet import defer
from trading_platform.contracts.orders import Management
from trading_platform.contracts.values import utc
from trading_platform.gateways.ctrader.projection import Projection
from trading_platform.gateways.ctrader.management import send_owned
from trading_platform.risk.sizing import Contract


class DemoAPI:
    def __init__(self,gateway,ledger,feed,reports,valuation,now,requirements=()):
        self.gateway=gateway;self.ledger=ledger;self.feed=feed;self.reports=reports
        self.valuation=valuation;self.now=now;self.projection=Projection(gateway.db);self.requirements=requirements

    def check(self,body):
        if str(body['account_id'])!=str(self.gateway.session.account_id): raise ValueError('foreign account')
        if not self.gateway.authorized: raise ValueError('demo orders disabled')
        self.gateway.fence.check(body['core_id'],body['epoch'])

    def view(self):
        now=self.now();value=self.valuation();blockers=[]
        if str(value.get('account_id'))!=str(self.gateway.session.account_id) or value.get('mode')!='demo': raise ValueError('valuation identity')
        if not 0<=(now-utc(value['observed_at'])).total_seconds()<=2: raise ValueError('stale valuation')
        if not value.get('evidence_hash') or value.get('classification') not in ('broker_verified','demo_observed'): blockers.append('UNVERIFIED_VALUATION')
        for field in ('balance','equity','free_margin'):
            amount=Decimal(value['account'][field])
            if not amount.is_finite() or (field!='free_margin' and amount<=0): raise ValueError('invalid account valuation')
        if not self.gateway.session.ready: blockers.append('DISCONNECTED')
        if not value.get('history_complete'): blockers.append('INCOMPLETE_HISTORY')
        # External exposure has no strategy risk allocation. Conservatively block entries.
        if value.get('external_exposure'): blockers.append('EXTERNAL_EXPOSURE')
        blockers.extend(self.projection.refresh(value.get('settlements')))
        return dict(mode='demo',account_id=str(self.gateway.session.account_id),observed_at=value['observed_at'],
                    account=value['account'],events=[json.loads(e.model_dump_json()) for e in self.projection.events()],blockers=blockers,
                    contracts=value.get('contracts',{}))

    def confirmed(self,command_id):
        row=self.projection.read('gateway-management:'+command_id)
        if not row: return False
        fields=row['fields'];request=row['request']
        if request=='ProtoOACancelOrderReq':
            target=self.projection.read('broker-order:'+str(fields['orderId']))
            return bool(target and target['terminal'])
        target=self.projection.read('broker-position:'+str(fields['positionId']))
        if not target or target['updated']<=row.get('target_revision',0): return False
        if request=='ProtoOAAmendPositionSLTPReq': return str(target['record'].get('stopLoss'))==str(fields['stopLoss']) or Decimal(str(target['record'].get('stopLoss',0)))==Decimal(str(fields['stopLoss']))
        if request=='ProtoOAClosePositionReq':
            return target['closed'] or Decimal(target['quantity'])<=Decimal(row['target_quantity'])-Decimal(fields['volume'])/100
        return False

    @defer.inlineCallbacks
    def handle(self,body):
        op=body['op']
        if op=='acquire':
            if not self.gateway.authorized or str(body['account_id'])!=str(self.gateway.session.account_id): raise ValueError('demo orders disabled or foreign account')
            return dict(mode='demo',authorized=True,account_id=str(self.gateway.session.account_id),epoch=self.gateway.fence.acquire(body['core_id']))
        self.check(body)
        if op=='observe': return self.view()
        if op=='snapshot':
            view=self.view()
            if view['blockers']: raise ValueError('snapshot reconciliation blocked')
            if not self.requirements: raise ValueError('explicit feed requirements required')
            return {'snapshot':json.loads(self.feed.snapshot(self.now(),self.requirements).model_dump_json()),'contracts':view['contracts']}
        if op=='recover':
            from .supervisor import ProtectionSupervisor
            supervisor=ProtectionSupervisor(self.gateway,self.ledger)
            view=self.view()
            if any(b in view['blockers'] for b in ('UNVERIFIED_VALUATION','INCOMPLETE_HISTORY')): raise ValueError('verified reconciliation required')
            observed=utc(view['observed_at']);actions={}
            for row in self.gateway.db.connection.execute("SELECT id FROM checkpoints WHERE id LIKE 'broker-position:%'").fetchall():
                pid=row['id'].split(':',1)[1]
                actions[pid]=supervisor.step(pid,body['core_id'],body['epoch'],self.now(),observed)
            return actions
        if op=='management_confirmed': return self.confirmed(body['command_id'])
        if op not in ('submit','manage'): raise ValueError('unsupported demo operation')
        command=body['command'];now=self.now()
        if op=='submit':
            view=self.view()
            if view['blockers']: raise ValueError('broker observation blocked')
            symbol=command['body']['decision']['proposal']['instrument']
            contract=Contract.model_validate_json(json.dumps(view['contracts'][symbol]))
            if contract.account_currency!=view['account']['currency'] or not 0<=(now-contract.verified_at).total_seconds()<=30: raise ValueError('unverified contract')
            if command['body']['contract']!=json.loads(contract.model_dump_json()): raise ValueError('valuation changed before send')
            raw=self.feed.get('quote:'+symbol)
            from trading_platform.contracts.events import Quote
            quote=Quote.model_validate_json(json.dumps(raw))
            result=yield self.gateway.send(command,body['core_id'],body['epoch'],self.reports[symbol],quote,now,utc(view['observed_at']))
        else:
            view=self.view()
            if any(b in view['blockers'] for b in ('DISCONNECTED','UNVERIFIED_VALUATION','INCOMPLETE_HISTORY')): raise ValueError('fresh verified reconciliation required')
            original=Management.model_validate_json(json.dumps(command['body']['decision']['proposal']))
            projected=self.projection.read('projection:'+original.target_id)
            send=self.projection.read('gateway-send:'+original.target_id)
            if not projected or not send or send['instance']!=command['instance'] or original.revision!=projected['revision']: raise ValueError('unowned/stale core management')
            order=self.projection.read('broker-order:'+send['broker_order_id'])
            target_id=send['broker_order_id'] if original.action=='cancel' else str(order['record'].get('positionId',''))
            target=(self.ledger.owned_order if original.action=='cancel' else self.ledger.owned)(target_id,command['instance'])
            original.authorize(command['instance'],send['instance'],projected['revision'],now)
            translated=original.model_copy(update={'target_id':target_id,'revision':target['updated']})
            result=yield send_owned(self.gateway,self.ledger,command['id'],command['instance'],translated,body['core_id'],body['epoch'],now)
        # SDK transport responses are execution facts, not assumed success.
        from ctrader_open_api import Protobuf
        from google.protobuf.json_format import MessageToDict
        payload=Protobuf.extract(result)
        if payload.DESCRIPTOR.name=='ProtoOAExecutionEvent': self.ledger.apply(MessageToDict(payload,preserving_proto_field_name=True))
        else: raise ValueError('request outcome requires reconciliation')
        self.projection.refresh(self.valuation().get('settlements'))
        return {'events':[json.loads(e.model_dump_json()) for e in self.projection.events()]}
