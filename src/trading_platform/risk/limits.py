import json
from decimal import Decimal as D
from datetime import timedelta
from zoneinfo import ZoneInfo
from trading_platform.contracts.values import canonical,utc


class Limits:
    def __init__(self,db,policy): self.db=db;self.policy=policy;self.key='risk:'+policy.alias

    def read(self,c):
        row=c.execute('SELECT body FROM checkpoints WHERE id=?',(self.key,)).fetchone()
        return json.loads(row['body']) if row else {}

    def save(self,c,state):
        c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(self.key,canonical(state)))

    def observe(self,at,equity,cumulative_flows=D(0)):
        day=at.astimezone(ZoneInfo('Europe/London')).date().isoformat()
        with self.db.transaction() as c:
            s=self.read(c)
            if s.get('day')!=day:
                s.update(day=day,start_equity=str(equity),start_flow=str(cumulative_flows),daily_halt=False)
            loss=D(s['start_equity'])+cumulative_flows-D(s['start_flow'])-equity
            if loss>=D(s['start_equity'])*self.policy.daily_loss: s['daily_halt']=True
            self.save(c,s)
        return s

    def check(self,c,now):
        s=self.read(c)
        day=now.astimezone(ZoneInfo('Europe/London')).date().isoformat()
        if s.get('day')!=day: raise ValueError('fresh daily equity observation required')
        if s.get('daily_halt'): raise ValueError('DAILY_LOSS_HALT')
        if s.get('cooldown') and now<utc(s['cooldown']): raise ValueError('LOSS_STREAK_COOLDOWN')
        if c.execute('SELECT 1 FROM halts').fetchone(): raise ValueError('ACCOUNT_HALT')

    def record_trade(self,trade_id,net,at):
        with self.db.transaction() as c: self.record_trade_in(c,trade_id,net,at)

    def record_trade_in(self,c,trade_id,net,at):
        key='trade:'+trade_id
        if c.execute('SELECT 1 FROM checkpoints WHERE id=?',(key,)).fetchone(): return
        s=self.read(c);s['streak']=s.get('streak',0)+1 if net<0 else 0
        if s['streak']>=3:
            s['cooldown']=(at+timedelta(minutes=60)).isoformat();s['streak']=0
        self.save(c,s);c.execute('INSERT INTO checkpoints VALUES (?,?)',(key,canonical({'net':net,'at':at})))
