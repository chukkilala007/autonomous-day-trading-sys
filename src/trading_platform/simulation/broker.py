"""Durable tick-driven simulator; every cost and fill assumption is explicit."""
import json,os
from pathlib import Path
from decimal import Decimal as D
from trading_platform.contracts.values import canonical,digest,utc
from trading_platform.contracts.orders import Entry,Management
from trading_platform.execution.state_machine import BrokerEvent


class PaperBroker:
    def __init__(self,path=None,*,price_slippage='0',max_fill=None):
        self.path=Path(path) if path else None
        self.slippage=D(price_slippage);self.max_fill=None if max_fill is None else D(max_fill)
        if self.slippage<0 or (self.max_fill is not None and self.max_fill<=0): raise ValueError('fill assumptions')
        self.state=json.loads(self.path.read_text()) if self.path and self.path.exists() else {'orders':{},'events':[],'management':{},'ticks':[],'quotes':{}}

    def save(self):
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.tmp')
            with temp.open('w') as f:
                f.write(canonical(self.state));f.flush();os.fsync(f.fileno())
            temp.replace(self.path)

    def events(self): return [BrokerEvent.model_validate_json(json.dumps(e)) for e in self.state['events']]
    def management_confirmed(self,id): return id in self.state['management']

    def emit(self,id,kind,at,**kw):
        o=self.state['orders'][id];o['revision']+=1;o['status']=kind
        kw.setdefault('open_quantity',o['open'])
        e=BrokerEvent(id=f'{id}:{o["revision"]}',command=id,revision=o['revision'],kind=kind,at=at,filled=o['filled'],average_price=o['average'],protected=o['protected'],**kw)
        self.state['events'].append(json.loads(e.model_dump_json()));return e

    def submit(self,cmd,quote,now,fault=None):
        if fault=='disconnect_before': raise OSError('injected disconnect')
        id=cmd['id']
        if id in self.state['orders']:
            if self.state['orders'][id]['command']['body']!=cmd['body']: raise ValueError('conflicting broker command')
            return [e for e in self.events() if e.command==id]
        start=len(self.state['events'])
        o={'command':cmd,'revision':-1,'status':'NEW','filled':'0','average':None,'open':'0','protected':True,'triggered':False,'submitted':now.isoformat(),'net':'0'}
        self.state['orders'][id]=o
        self.emit(id,'REJECTED' if fault=='reject' else 'ACCEPTED',now)
        if fault!='reject': self.fill(id,quote,now)
        self.save()
        if fault=='timeout_after_accept': raise TimeoutError('accepted but acknowledgement lost')
        return self.events()[start:]

    def fill(self,id,q,now):
        o=self.state['orders'][id];p=Entry.model_validate_json(json.dumps(o['command']['body']['decision']['proposal']))
        total=D(o['command']['body']['size']['quantity']);filled=D(o['filled'])
        if filled>=total or o['status'] in ('CANCELLED','EXPIRED','REJECTED','CLOSED'): return
        if q.instrument!=p.instrument or q.source_time<utc(o['submitted']): return
        if now>=p.expires_at:
            self.emit(id,'EXPIRED',now);return
        side=1 if p.side=='buy' else -1
        current=q.ask if side==1 else q.bid
        price=current+self.slippage*side
        if p.order_type in ('stop','stop_limit'):
            o['triggered']=o['triggered'] or (current>=p.entry if side==1 else current<=p.entry)
            if not o['triggered']: return
        if p.order_type in ('limit','stop_limit'):
            limit=p.limit if p.order_type=='stop_limit' else p.entry
            if (side==1 and price>limit) or (side==-1 and price<limit): return
        if (side==1 and price>p.worst_fill) or (side==-1 and price<p.worst_fill):
            if p.order_type=='market': self.emit(id,'REJECTED',now)
            return
        quantity=min(total-filled,self.max_fill or total)
        old_average=D(o['average']) if o['average'] else D(0)
        average=(old_average*filled+price*quantity)/(filled+quantity)
        o.update(filled=str(filled+quantity),average=str(average),open=str(D(o['open'])+quantity))
        self.emit(id,'FILLED' if filled+quantity==total else 'PART_FILLED',now)

    def close(self,id,price,now,quantity=None):
        o=self.state['orders'][id];p=Entry.model_validate_json(json.dumps(o['command']['body']['decision']['proposal']))
        quantity=D(o['open']) if quantity is None else quantity
        if quantity<=0 or quantity>D(o['open']): raise ValueError('invalid close quantity')
        c=o['command']['body']['contract']
        direction=1 if p.side=='buy' else -1
        net=(price-D(o['average']))*direction*quantity*D(c['contract_value_per_unit'])*D(c['quote_to_account'])-D(c['commission_per_unit'])*quantity
        o['net']=str(D(o['net'])+net);o['open']=str(D(o['open'])-quantity)
        if D(o['open'])==0: self.emit(id,'CLOSED',now,net=o['net'],open_quantity='0')
        else: self.emit(id,'REDUCED',now,net=o['net'],open_quantity=o['open'])

    def tick(self,q,now):
        if q.received_at>now or not 0<=(now-q.source_time).total_seconds()<=2: raise ValueError('stale tick')
        key=digest(q)
        if key in self.state['ticks']: return []
        previous=self.state['quotes'].get(q.instrument)
        if previous and utc(previous['source_time'])>q.source_time: raise ValueError('out of order tick')
        self.state['quotes'][q.instrument]=json.loads(q.model_dump_json());self.state['ticks'].append(key)
        start=len(self.state['events'])
        for id,o in self.state['orders'].items():
            p=Entry.model_validate_json(json.dumps(o['command']['body']['decision']['proposal']))
            if p.instrument!=q.instrument or o['status']=='CLOSED': continue
            self.fill(id,q,now)
            if D(o['open'])>0:
                exit_price=q.bid-self.slippage if p.side=='buy' else q.ask+self.slippage
                stop=(exit_price<=p.stop if p.side=='buy' else exit_price>=p.stop)
                target=p.target is not None and (exit_price>=p.target if p.side=='buy' else exit_price<=p.target)
                if stop or target or (p.exit_at and now>=p.exit_at): self.close(id,exit_price,now)
        self.save();return self.events()[start:]

    def manage(self,cmd,now,fault=None):
        id=cmd['id'];m=Management.model_validate_json(json.dumps(cmd['body']['decision']['proposal']))
        if id in self.state['management']: return []
        o=self.state['orders'].get(m.target_id)
        if o is None: raise ValueError('unknown broker target')
        m.authorize(cmd['instance'],o['command']['instance'],o['revision'],now)
        start=len(self.state['events'])
        if m.action=='cancel':
            self.emit(m.target_id,'CANCELLED',now)
        elif m.action=='protect':
            o['command']['body']['decision']['proposal']['stop']=str(m.stop)
            self.emit(m.target_id,'PROTECTED',now,stop=m.stop,open_quantity=o['open'])
        else:
            from trading_platform.contracts.events import Quote
            instrument=o['command']['instrument'];raw=self.state['quotes'].get(instrument)
            if raw is None: raise ValueError('fresh exit quote required')
            q=Quote.model_validate_json(json.dumps(raw))
            if not 0<=(now-q.source_time).total_seconds()<=2: raise ValueError('fresh exit quote required')
            side=o['command']['body']['decision']['proposal']['side']
            price=q.bid-self.slippage if side=='buy' else q.ask+self.slippage
            self.close(m.target_id,price,now,m.quantity if m.action=='reduce' else None)
        self.state['management'][id]=True;self.save()
        if fault=='timeout_after_accept': raise TimeoutError('management acknowledgement lost')
        return self.events()[start:]
