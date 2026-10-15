"""TPR-1 causal structural detector. Standard library only; no broker actions."""
from __future__ import annotations
import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

VERSION = 'TPR-1'
PARAMETERS = {
    'EURUSD': {'tolerance': '0.00005', 'price_step': '0.00001'},
    'XAUUSD': {'tolerance': '0.30', 'price_step': '0.01'},
}

def epoch(value):
    if isinstance(value, int):
        return value
    if not isinstance(value,str):
        raise TypeError('Timestamp must be timezone-aware ISO text or epoch seconds')
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return int(t.timestamp())

def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat().replace('+00:00', 'Z')

def decimal(value):
    x = D(str(value))
    if not x.is_finite():
        raise ValueError('Nonfinite price')
    return x

@dataclass(frozen=True)
class Bar:
    t: int
    o: D
    h: D
    l: D
    c: D

    @classmethod
    def read(cls, b):
        r = cls(epoch(b['timestamp']), *(decimal(b[k]) for k in ('open','high','low','close')))
        if r.h < max(r.o, r.c) or r.l > min(r.o, r.c):
            raise ValueError('Invalid OHLC')
        return r

def bars(raw, interval, cutoff=None):
    out = [b if isinstance(b, Bar) else Bar.read(b) for b in raw]
    if any(b.t % interval for b in out):
        raise ValueError('Nonaligned bar timestamp')
    if any(a.t >= b.t for a, b in zip(out, out[1:])):
        raise ValueError('Duplicate or unsorted timestamps')
    return [b for b in out if cutoff is None or b.t + interval <= cutoff]

def pivots(history, interval=300):
    """Caller supplies only completed M5 bars. Last two cannot be pivots yet."""
    highs, lows = [], []
    for i in range(2, len(history)-2):
        b = history[i]
        neighbours = history[i-2:i] + history[i+1:i+3]
        # Do not call a five-bar formation spanning missing intervals a pivot.
        window = history[i-2:i+3]
        if any(y.t-x.t != interval for x,y in zip(window, window[1:])):
            continue
        if all(b.h > n.h for n in neighbours):
            highs.append(b)
        if all(b.l < n.l for n in neighbours):
            lows.append(b)
    return highs, lows

def rejection(b, direction, lo, hi):
    width = b.h-b.l
    if width <= 0 or b.l > hi or b.h < lo:
        return False
    if direction == 'long':
        return b.c > b.o and b.c > hi and (b.c-b.l)*3 >= width*2 and b.o-b.l >= b.c-b.o
    return b.c < b.o and b.c < lo and (b.c-b.l)*3 <= width and b.h-b.o >= b.o-b.c

def structural_plan(direction, trigger, extreme, step, targets):
    entry = trigger.h+step if direction == 'long' else trigger.l-step
    stop = extreme-2*step if direction == 'long' else extreme+2*step
    risk = entry-stop if direction == 'long' else stop-entry
    eligible = [v for v in targets if v['price'] > entry] if direction == 'long' else [v for v in targets if v['price'] < entry]
    if not eligible:
        return None, ['NO_TARGET']
    target = min(eligible, key=lambda v: v['price']) if direction == 'long' else max(eligible, key=lambda v: v['price'])
    reward = abs(target['price']-entry)
    if risk <= 0:
        raise ValueError('Nonpositive structural risk')
    rr = reward/risk
    plan = {k: str(v) for k,v in {'entry':entry,'stop':stop,'tp1':target['price'],'risk':risk,'reward':reward,'gross_rr':rr}.items()}
    plan.update(target_anchor=target['anchor'], target_kind=target['kind'], geometry_basis='research_candle_reference')
    return plan, [] if rr >= 2 else ['INSUFFICIENT_RR']

def cost_reasons(plan, spread):
    if spread is None:
        return ['COST_UNKNOWN']
    spread = decimal(spread)
    if spread < 0:
        raise ValueError('Negative spread')
    return [code for code,key in [('COST_STOP','risk'),('COST_REWARD','reward')]
            if spread > D('.2')*decimal(plan[key])]

def execution_check(plan, quote, metadata, now, *, available=False, direction=None):
    """No timestamp/grid/basis fallback. Provenance must come from provider evidence."""
    reasons = []
    spread = None
    bid = ask = None
    try:
        bid, ask = decimal(quote['bid']), decimal(quote['ask'])
        if bid <= 0 or ask < bid:
            raise ValueError('Invalid quote')
        spread = ask-bid
    except (KeyError, TypeError, ValueError, ArithmeticError):
        reasons.append('QUOTE_INVALID')
    source = quote.get('source_time')
    if source is None:
        reasons.append('SOURCE_TIME_MISSING')
    else:
        try:
            age = now-epoch(source)
            if not 0 <= age <= 30:
                reasons.append('STALE_QUOTE')
        except (ValueError, TypeError):
            reasons.append('STALE_QUOTE')
    if metadata.get('actual_session_open') is False:
        reasons.append('SESSION_CLOSED')
    elif metadata.get('actual_session_open') is not True:
        reasons.append('METADATA_MISSING')
    try:
        if not 0 <= now-epoch(metadata['session_source_time']) <= 30:
            reasons.append('SESSION_STATE_STALE')
    except (KeyError,TypeError,ValueError):
        reasons.append('SESSION_STATE_STALE')
    if metadata.get('price_basis') not in ('bid','ask') or plan.get('geometry_basis') != 'executable':
        reasons.append('PRICE_BASIS_UNKNOWN')
    evidence = metadata.get('provenance', {})
    if not all(evidence.get(k) for k in ('tick_size','actual_session_open','price_basis')):
        reasons.append('METADATA_MISSING')
    tick = metadata.get('tick_size')
    try:
        tick = decimal(tick)
        if tick <= 0 or any(decimal(plan[k]) % tick for k in ('entry','stop','tp1')):
            reasons.append('PRICE_GRID')
    except (TypeError, ValueError, ArithmeticError):
        reasons.append('PRICE_GRID')
    reasons += cost_reasons(plan, spread)
    if direction in ('long','short'):
        entry,stop,tp1=(decimal(plan[k]) for k in ('entry','stop','tp1'))
        risk=entry-stop if direction=='long' else stop-entry
        reward=tp1-entry if direction=='long' else entry-tp1
        if risk<=0 or reward<=0:
            reasons.append('INVALID_GEOMETRY')
        else:
            if risk!=decimal(plan['risk']) or reward!=decimal(plan['reward']) or abs(reward/risk-decimal(plan['gross_rr']))>D('0.00000001'):
                reasons.append('INVALID_GEOMETRY')
            if reward/risk<2: reasons.append('INSUFFICIENT_RR')
    if not available:
        reasons.append('AVAILABILITY_UNVERIFIED')
    try:
        if not 0 <= now-epoch(metadata['availability_asof']) <= 60:
            reasons.append('AVAILABILITY_UNVERIFIED')
    except (KeyError,TypeError,ValueError):
        reasons.append('AVAILABILITY_UNVERIFIED')
    if metadata.get('context_screen_complete') is not True:
        reasons.append('HTF_SCREEN_INCOMPLETE')
    if direction not in ('long','short'):
        reasons.append('DIRECTION_MISSING')
    elif bid is not None and ask is not None:
        if (direction == 'long' and ask >= decimal(plan['entry'])) or (direction == 'short' and bid <= decimal(plan['entry'])):
            reasons.append('ENTRY_TOUCHED')
    reasons = list(dict.fromkeys(reasons))
    state = 'VERIFIED' if not reasons else 'UNVERIFIED'
    if any(r.startswith('COST_') and r != 'COST_UNKNOWN' for r in reasons): state = 'COST_FAIL'
    if 'STALE_QUOTE' in reasons: state = 'STALE'
    if 'SESSION_CLOSED' in reasons: state = 'CLOSED'
    return {'execution_state':state,'entry_ready':not reasons,'reasons':reasons,'spread':None if spread is None else str(spread)}

@dataclass
class Candidate:
    id: str
    direction: str
    level: D
    lo: D
    hi: D
    invalidation: D
    born: int
    expires: int
    level_anchor: int
    impulse_extreme: D
    impulse_anchor: int
    state: str = 'FORMING'
    touched: bool = False
    pullback_extreme: D | None = None
    trigger_end: int | None = None
    entry_expires: int | None = None
    plan: dict | None = None
    reasons: list = field(default_factory=list)

class Engine:
    def __init__(self, symbol, m5, tolerance=None, price_step=None, context=None):
        cfg = PARAMETERS[symbol]
        self.symbol = symbol
        self.tolerance = decimal(tolerance or cfg['tolerance'])
        self.step = decimal(price_step or cfg['price_step'])
        if self.tolerance <= 0 or self.step <= 0: raise ValueError('Positive parameters required')
        self.m5 = bars(m5, 300)
        self.context = {tf:bars(raw,seconds) for tf,seconds in [('m15',900),('h1',3600)]
                        if context and (raw:=context.get(tf)) is not None}
        self.now = None
        self.history = []
        self.index = 0
        self.last_m1 = None
        self.candidate = None
        self.events = []
        self.diagnostics = {'NO_TREND':0,'NO_IMPULSE':0,'SUPPRESSED_IMPULSE':0}

    def event(self, at, kind, **fields):
        c = self.candidate
        row = {'candidate_id':c.id,'symbol':self.symbol,'decision_time':iso(at),'event':kind,
               'setup_state':c.state,'direction':c.direction,'level':str(c.level),
               'zone':[str(c.lo),str(c.hi)],'level_anchor':iso(c.level_anchor),
               'invalidation':str(c.invalidation),'pattern_expires':iso(c.expires),
               'plan':None if c.plan is None else dict(c.plan),'reason_codes':list(c.reasons)}
        row.update(fields)
        self.events.append(row)

    def close_candidate(self, at, state, reason):
        self.candidate.state = state
        self.candidate.reasons = [reason]
        self.event(at, state)

    def new_impulse(self, b):
        # Pivots were confirmed at/before this M5 candle's opening time.
        prior = [v for v in self.history if v.t+300 <= b.t][-72:]
        highs, lows = pivots(prior)
        if len(highs)<2 or len(lows)<2 or not prior:
            self.diagnostics['NO_TREND'] += 1
            return
        direction = None
        if highs[-1].h>highs[-2].h and lows[-1].l>lows[-2].l: direction='long'
        if highs[-1].h<highs[-2].h and lows[-1].l<lows[-2].l: direction='short'
        if direction is None:
            self.diagnostics['NO_TREND'] += 1
            return
        pivot = highs[-1] if direction=='long' else lows[-1]
        level = pivot.h if direction=='long' else pivot.l
        inv = lows[-1].l if direction=='long' else highs[-1].h
        lo,hi = level-self.tolerance,level+self.tolerance
        crossing = (prior[-1].c<=hi and b.c>hi and inv<lo) if direction=='long' else (prior[-1].c>=lo and b.c<lo and inv>hi)
        if not crossing:
            self.diagnostics['NO_IMPULSE'] += 1
            return
        if self.candidate and self.candidate.state in ('FORMING','TRIGGERED'):
            self.diagnostics['SUPPRESSED_IMPULSE'] += 1
            return
        born=b.t+300
        self.candidate=Candidate(f'{VERSION}/{self.symbol}/{direction}/{pivot.t}/{b.t}',direction,
             level,lo,hi,inv,born,born+1800,pivot.t,b.h if direction=='long' else b.l,b.t)
        self.event(born,'FORMING',next_trigger='zone touch followed by completed M1 rejection')

    def target_levels(self, c):
        out=[{'price':c.impulse_extreme,'anchor':iso(c.impulse_anchor),'kind':'impulse_boundary'}]
        series=[('m5',300,self.history[-72:])]
        for tf,seconds in [('m15',900),('h1',3600)]:
            series.append((tf,seconds,[b for b in self.context.get(tf,[]) if b.t+seconds<=self.now]))
        for tf,seconds,history in series:
            highs,lows=pivots(history,seconds)
            for p in highs if c.direction=='long' else lows:
                price=p.h if c.direction=='long' else p.l
                after=[b for b in history if b.t>p.t]
                retired=any(b.c>price for b in after) if c.direction=='long' else any(b.c<price for b in after)
                if not retired:
                    out.append({'price':price,'anchor':iso(p.t),'kind':f'active_confirmed_{tf}_swing'})
        return out

    def context_complete(self):
        for tf,seconds,minimum in [('m15',900,20),('h1',3600,12)]:
            history=[b for b in self.context.get(tf,[]) if b.t+seconds<=self.now]
            if len(history)<minimum or history[-1].t+seconds != (self.now//seconds)*seconds:
                return False
        return True

    def step_bar(self, b):
        end=b.t+60
        self.now=end
        if self.last_m1 is not None and b.t<=self.last_m1:
            raise ValueError('M1 must advance strictly')
        gap=self.last_m1 is not None and b.t-self.last_m1!=60
        if gap and self.candidate and self.candidate.state in ('FORMING','TRIGGERED'):
            self.close_candidate(end,'DATA_UNAVAILABLE','DATA_GAP')
        # History can span sessions for context, but do not originate an active
        # candidate in M5 intervals with no observed corresponding M1 sequence.
        while self.index<len(self.m5) and self.m5[self.index].t+300<=end:
            m=self.m5[self.index]
            if m.t+300==end and not gap:
                self.new_impulse(m)
            self.history.append(m)
            self.index+=1
        self.last_m1=b.t
        c=self.candidate
        if not c or c.state not in ('FORMING','TRIGGERED') or b.t<c.born:
            return
        if b.t>=c.expires or (c.state=='FORMING' and end>=c.expires):
            self.close_candidate(end,'EXPIRED','FORMING_EXPIRED')
            return
        if c.state=='TRIGGERED':
            if b.t>=c.entry_expires:
                self.close_candidate(end,'EXPIRED','ENTRY_EXPIRED')
                return
            entry,stop=decimal(c.plan['entry']),decimal(c.plan['stop'])
            et=b.h>=entry if c.direction=='long' else b.l<=entry
            st=b.l<=max(stop,c.invalidation) if c.direction=='long' else b.h>=min(stop,c.invalidation)
            if et and st: self.close_candidate(end,'MISSED','AMBIGUOUS_TOUCH')
            elif st: self.close_candidate(end,'INVALIDATED','STOP_BEFORE_ENTRY')
            elif et: self.close_candidate(end,'MISSED','ENTRY_TOUCHED')
            elif end>=c.entry_expires: self.close_candidate(end,'EXPIRED','ENTRY_EXPIRED')
            return
        invalid=b.l<=c.invalidation if c.direction=='long' else b.h>=c.invalidation
        if invalid:
            self.close_candidate(end,'INVALIDATED','TREND_INVALIDATED')
            return
        overlap=b.l<=c.hi and b.h>=c.lo
        # Targets use only the impulse/pullback observed BEFORE this trigger bar.
        targets=self.target_levels(c)
        if overlap or c.touched:
            if not c.touched:
                c.touched=True
                self.event(end,'PULLBACK_TOUCH',next_trigger='completed M1 rejection at frozen zone')
            value=b.l if c.direction=='long' else b.h
            c.pullback_extreme=value if c.pullback_extreme is None else (min(c.pullback_extreme,value) if c.direction=='long' else max(c.pullback_extreme,value))
            if rejection(b,c.direction,c.lo,c.hi):
                c.plan,c.reasons=structural_plan(c.direction,b,c.pullback_extreme,self.step,targets)
                c.trigger_end=end
                c.entry_expires=min(end+180,c.expires)
                c.state='TRIGGERED'
                self.event(end,'TRIGGERED',trigger_open=iso(b.t),entry_expires=iso(c.entry_expires),
                           geometry_pass=not c.reasons,execution_state='UNVERIFIED',
                           context_screen_complete=self.context_complete(),
                           execution_reasons=['COST_UNKNOWN','METADATA_MISSING']+([] if self.context_complete() else ['HTF_SCREEN_INCOMPLETE']))
                if c.reasons:
                    c.state='REJECTED'
                    self.event(end,'REJECTED')
                return
        if c.direction=='long' and b.h>c.impulse_extreme:
            c.impulse_extreme,c.impulse_anchor=b.h,b.t
        if c.direction=='short' and b.l<c.impulse_extreme:
            c.impulse_extreme,c.impulse_anchor=b.l,b.t

    def run(self, m1):
        for b in bars(m1,60): self.step_bar(b)
        return {'version':VERSION,'symbol':self.symbol,'parameters':{
             'tolerance':str(self.tolerance),'research_price_step':str(self.step),
             'min_gross_rr':'2','forming_seconds':1800,'pending_bars':3,'m5_lookback':72},
             'events':self.events,'diagnostics':self.diagnostics,
             'current_candidate':None if self.candidate is None else {
                 'id':self.candidate.id,'setup_state':self.candidate.state,
                 'direction':self.candidate.direction,'zone':[str(self.candidate.lo),str(self.candidate.hi)],
                 'invalidation':str(self.candidate.invalidation),'plan':self.candidate.plan,
                 'reason_codes':self.candidate.reasons,'pattern_expires':iso(self.candidate.expires),
                 'entry_expires':None if self.candidate.entry_expires is None else iso(self.candidate.entry_expires)},
             'last_m1_close':None if self.last_m1 is None else iso(self.last_m1+60),
             'limitations':['historical costs unknown','execution unverified','context completeness recorded per trigger','events are not trades']}

def from_snapshot(document,symbol):
    cutoff=epoch(document['cutoff'])
    x=document['symbols'][symbol]
    context={tf:bars(x[tf]['completed'],seconds,cutoff) for tf,seconds in [('m15',900),('h1',3600)] if tf in x and 'completed' in x[tf]}
    return Engine(symbol,bars(x['m5']['completed'],300,cutoff),context=context).run(bars(x['m1']['completed'],60,cutoff))

def persist_state(directory,result,observed_at):
    """Deduplicate repeated scans, while retaining changed observations explicitly."""
    directory=Path(directory)/VERSION
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/(result['symbol']+'.json')
    existing=json.loads(path.read_text()) if path.exists() else {'version':VERSION,'events':[],'revisions':[]}
    keys=lambda e:(e['candidate_id'],e['event'],e['decision_time'])
    index={keys(e):e for e in existing['events']}
    for event in result['events']:
        key=keys(event)
        if key in index and index[key]!=event:
            existing['revisions'].append({'observed_at':observed_at,'previous':index[key],'updated':event})
        index[key]=event
    existing['events']=sorted(index.values(),key=lambda e:(e['decision_time'],e['candidate_id'],e['event']))
    existing.update(symbol=result['symbol'],parameters=result['parameters'],observed_at=observed_at,
                    current_candidate=result['current_candidate'])
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(existing,indent=2));temp.replace(path)
    return path

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--symbol',required=True,choices=PARAMETERS)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--state-dir',type=Path,help='Optional live scan state directory; omit for offline replay')
    args=parser.parse_args()
    result=from_snapshot(json.loads(args.input.read_text()),args.symbol)
    with args.output.open('x') as f: json.dump(result,f,indent=2)
    if args.state_dir: persist_state(args.state_dir,result,datetime.now(timezone.utc).isoformat())
