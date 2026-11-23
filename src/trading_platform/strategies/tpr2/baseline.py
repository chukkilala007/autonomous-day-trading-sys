"""TPR-2 causal detector: frozen structure plus a post-rejection limit retest."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal as D

VERSION = 'TPR-2'
PARAMETERS = {
    'EURUSD': {'tolerance': '0.00005', 'price_step': '0.00001'},
    'XAUUSD': {'tolerance': '0.30', 'price_step': '0.01'},
}


def epoch(value):
    if isinstance(value, int): return value
    if not isinstance(value, str): raise TypeError('Timestamp must be timezone-aware ISO text or epoch seconds')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None: raise ValueError('Timestamp requires timezone')
    return int(parsed.timestamp())


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def decimal(value):
    parsed = D(str(value))
    if not parsed.is_finite(): raise ValueError('Nonfinite price')
    return parsed


@dataclass(frozen=True)
class Bar:
    t: int
    o: D
    h: D
    l: D
    c: D

    @classmethod
    def read(cls, raw):
        result = cls(epoch(raw['timestamp']), *(decimal(raw[k]) for k in ('open', 'high', 'low', 'close')))
        if result.h < max(result.o, result.c) or result.l > min(result.o, result.c):
            raise ValueError('Invalid OHLC')
        return result


def bars(raw, interval, cutoff=None):
    result = [value if isinstance(value, Bar) else (
        Bar(value.t, decimal(value.o), decimal(value.h), decimal(value.l), decimal(value.c))
        if all(hasattr(value, name) for name in ('t', 'o', 'h', 'l', 'c')) else Bar.read(value)) for value in raw]
    if any(value.t % interval for value in result): raise ValueError('Nonaligned bar timestamp')
    if any(left.t >= right.t for left, right in zip(result, result[1:])):
        raise ValueError('Duplicate or unsorted timestamps')
    return [value for value in result if cutoff is None or value.t+interval <= cutoff]


def pivots(history, interval=300):
    highs, lows = [], []
    for index in range(2, len(history)-2):
        value = history[index]; window = history[index-2:index+3]
        if any(right.t-left.t != interval for left, right in zip(window, window[1:])): continue
        neighbours = history[index-2:index]+history[index+1:index+3]
        if all(value.h > other.h for other in neighbours): highs.append(value)
        if all(value.l < other.l for other in neighbours): lows.append(value)
    return highs, lows


def rejection(value, direction, low, high):
    width = value.h-value.l
    if width <= 0 or value.l > high or value.h < low: return False
    if direction == 'long':
        return (value.c > value.o and value.c > high and (value.c-value.l)*3 >= width*2
                and value.o-value.l >= value.c-value.o)
    return (value.c < value.o and value.c < low and (value.c-value.l)*3 <= width
            and value.h-value.o >= value.o-value.c)


def cost_reasons(plan, spread):
    if spread is None: return ['COST_UNKNOWN']
    spread = decimal(spread)
    if spread < 0: raise ValueError('Negative spread')
    return [code for code, key in [('COST_STOP', 'risk'), ('COST_REWARD', 'reward')]
            if spread > D('.2')*decimal(plan[key])]


def execution_check(plan, quote, metadata, now, *, available=False, direction=None):
    reasons = []; spread = None; bid = ask = None
    try:
        bid, ask = decimal(quote['bid']), decimal(quote['ask'])
        if bid <= 0 or ask < bid: raise ValueError('Invalid quote')
        spread = ask-bid
    except (KeyError, TypeError, ValueError, ArithmeticError): reasons.append('QUOTE_INVALID')
    try:
        age = now-epoch(quote['source_time'])
        if not 0 <= age <= 30: reasons.append('STALE_QUOTE')
    except (KeyError, TypeError, ValueError): reasons.append('SOURCE_TIME_MISSING')
    if metadata.get('actual_session_open') is False: reasons.append('SESSION_CLOSED')
    elif metadata.get('actual_session_open') is not True: reasons.append('METADATA_MISSING')
    try:
        if not 0 <= now-epoch(metadata['session_source_time']) <= 30: reasons.append('SESSION_STATE_STALE')
    except (KeyError, TypeError, ValueError): reasons.append('SESSION_STATE_STALE')
    if metadata.get('price_basis') not in ('bid', 'ask') or plan.get('geometry_basis') != 'executable':
        reasons.append('PRICE_BASIS_UNKNOWN')
    evidence = metadata.get('provenance', {})
    if not all(evidence.get(k) for k in ('tick_size', 'actual_session_open', 'price_basis')):
        reasons.append('METADATA_MISSING')
    try:
        tick = decimal(metadata.get('tick_size'))
        if tick <= 0 or any(decimal(plan[k]) % tick for k in ('entry', 'stop', 'tp1')):
            reasons.append('PRICE_GRID')
    except (TypeError, ValueError, ArithmeticError): reasons.append('PRICE_GRID')
    reasons += cost_reasons(plan, spread)
    if direction in ('long', 'short'):
        entry, stop, target = (decimal(plan[k]) for k in ('entry', 'stop', 'tp1'))
        risk = entry-stop if direction == 'long' else stop-entry
        reward = target-entry if direction == 'long' else entry-target
        if risk <= 0 or reward <= 0: reasons.append('INVALID_GEOMETRY')
        elif (risk != decimal(plan['risk']) or reward != decimal(plan['reward'])
              or abs(reward/risk-decimal(plan['gross_rr'])) > D('0.00000001')):
            reasons.append('INVALID_GEOMETRY')
        if risk > 0 and reward/risk < 2: reasons.append('INSUFFICIENT_RR')
    else: reasons.append('DIRECTION_MISSING')
    if not available: reasons.append('AVAILABILITY_UNVERIFIED')
    try:
        if not 0 <= now-epoch(metadata['availability_asof']) <= 60: reasons.append('AVAILABILITY_UNVERIFIED')
    except (KeyError, TypeError, ValueError): reasons.append('AVAILABILITY_UNVERIFIED')
    if metadata.get('context_screen_complete') is not True: reasons.append('HTF_SCREEN_INCOMPLETE')
    reasons = list(dict.fromkeys(reasons)); state = 'VERIFIED' if not reasons else 'UNVERIFIED'
    if any(r.startswith('COST_') and r != 'COST_UNKNOWN' for r in reasons): state = 'COST_FAIL'
    if 'STALE_QUOTE' in reasons: state = 'STALE'
    if 'SESSION_CLOSED' in reasons: state = 'CLOSED'
    return {'execution_state': state, 'entry_ready': not reasons, 'reasons': reasons,
            'spread': None if spread is None else str(spread)}


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
    step: D | None = None


def structural_plan(direction, candidate, targets):
    """Freeze a limit at the reclaimed-zone edge after rejection completes."""
    entry = candidate.hi if direction == 'long' else candidate.lo
    stop = (candidate.pullback_extreme - 2*candidate_step(candidate)) if direction == 'long' else (
        candidate.pullback_extreme + 2*candidate_step(candidate))
    risk = entry-stop if direction == 'long' else stop-entry
    eligible = [v for v in targets if v['price'] > entry] if direction == 'long' else [
        v for v in targets if v['price'] < entry]
    if not eligible:
        return None, ['NO_TARGET']
    target = min(eligible, key=lambda v: v['price']) if direction == 'long' else max(
        eligible, key=lambda v: v['price'])
    reward = abs(target['price']-entry)
    if risk <= 0:
        raise ValueError('Nonpositive structural risk')
    rr = reward/risk
    plan = {k: str(v) for k, v in {'entry': entry, 'stop': stop, 'tp1': target['price'],
            'risk': risk, 'reward': reward, 'gross_rr': rr}.items()}
    plan.update(target_anchor=target['anchor'], target_kind=target['kind'],
                geometry_basis='research_candle_reference', entry_semantics='post_rejection_limit_retest')
    return plan, [] if rr >= 2 else ['INSUFFICIENT_RR']


def candidate_step(candidate):
    return candidate.step


class Engine:
    """Keeps the preregistered trend/rejection rules but changes entry semantics."""
    def __init__(self, symbol, m5, tolerance=None, price_step=None, context=None):
        cfg = PARAMETERS[symbol]; self.symbol = symbol
        self.tolerance = decimal(tolerance or cfg['tolerance']); self.step = decimal(price_step or cfg['price_step'])
        if self.tolerance <= 0 or self.step <= 0: raise ValueError('Positive parameters required')
        self.m5 = bars(m5, 300)
        self.context = {tf: bars(raw, seconds) for tf, seconds in [('m15', 900), ('h1', 3600)]
                        if context and (raw := context.get(tf)) is not None}
        self.now = None; self.history = []; self.index = 0; self.last_m1 = None
        self.candidate = None; self.events = []
        self.diagnostics = {'NO_TREND': 0, 'NO_IMPULSE': 0, 'SUPPRESSED_IMPULSE': 0}

    def event(self, at, kind, **fields):
        candidate = self.candidate
        row = {'candidate_id': candidate.id, 'symbol': self.symbol, 'decision_time': iso(at),
            'event': kind, 'setup_state': candidate.state, 'direction': candidate.direction,
            'level': str(candidate.level), 'zone': [str(candidate.lo), str(candidate.hi)],
            'level_anchor': iso(candidate.level_anchor), 'invalidation': str(candidate.invalidation),
            'pattern_expires': iso(candidate.expires),
            'plan': None if candidate.plan is None else dict(candidate.plan),
            'reason_codes': list(candidate.reasons)}
        row.update(fields); self.events.append(row)

    def close_candidate(self, at, state, reason):
        self.candidate.state = state; self.candidate.reasons = [reason]; self.event(at, state)

    def new_impulse(self, b):
        prior = [v for v in self.history if v.t+300 <= b.t][-72:]
        highs, lows = pivots(prior)
        if len(highs) < 2 or len(lows) < 2 or not prior:
            self.diagnostics['NO_TREND'] += 1; return
        direction = None
        if highs[-1].h > highs[-2].h and lows[-1].l > lows[-2].l: direction = 'long'
        if highs[-1].h < highs[-2].h and lows[-1].l < lows[-2].l: direction = 'short'
        if direction is None:
            self.diagnostics['NO_TREND'] += 1; return
        pivot = highs[-1] if direction == 'long' else lows[-1]
        level = pivot.h if direction == 'long' else pivot.l
        inv = lows[-1].l if direction == 'long' else highs[-1].h
        lo, hi = level-self.tolerance, level+self.tolerance
        crossing = (prior[-1].c <= hi and b.c > hi and inv < lo) if direction == 'long' else (
            prior[-1].c >= lo and b.c < lo and inv > hi)
        if not crossing:
            self.diagnostics['NO_IMPULSE'] += 1; return
        if self.candidate and self.candidate.state in ('FORMING', 'TRIGGERED'):
            self.diagnostics['SUPPRESSED_IMPULSE'] += 1; return
        born = b.t+300
        self.candidate = Candidate(f'{VERSION}/{self.symbol}/{direction}/{pivot.t}/{b.t}', direction,
            level, lo, hi, inv, born, born+1800, pivot.t,
            b.h if direction == 'long' else b.l, b.t, step=self.step)
        self.event(born, 'FORMING', next_trigger='zone touch followed by completed M1 rejection')

    def target_levels(self, candidate):
        result = [{'price': candidate.impulse_extreme, 'anchor': iso(candidate.impulse_anchor),
                   'kind': 'impulse_boundary'}]
        series = [('m5', 300, self.history[-72:])]
        for timeframe, seconds in [('m15', 900), ('h1', 3600)]:
            series.append((timeframe, seconds, [b for b in self.context.get(timeframe, []) if b.t+seconds <= self.now]))
        for timeframe, seconds, history in series:
            highs, lows = pivots(history, seconds)
            for pivot in highs if candidate.direction == 'long' else lows:
                price = pivot.h if candidate.direction == 'long' else pivot.l
                after = [b for b in history if b.t > pivot.t]
                retired = any(b.c > price for b in after) if candidate.direction == 'long' else any(b.c < price for b in after)
                if not retired: result.append({'price': price, 'anchor': iso(pivot.t),
                                                'kind': f'active_confirmed_{timeframe}_swing'})
        return result

    def context_complete(self):
        for timeframe, seconds, minimum in [('m15', 900, 20), ('h1', 3600, 12)]:
            history = [b for b in self.context.get(timeframe, []) if b.t+seconds <= self.now]
            if len(history) < minimum or history[-1].t+seconds != (self.now//seconds)*seconds: return False
        return True

    def step_bar(self, b):
        end = b.t+60; self.now = end
        if self.last_m1 is not None and b.t <= self.last_m1: raise ValueError('M1 must advance strictly')
        gap = self.last_m1 is not None and b.t-self.last_m1 != 60
        if gap and self.candidate and self.candidate.state in ('FORMING', 'TRIGGERED'):
            self.close_candidate(end, 'DATA_UNAVAILABLE', 'DATA_GAP')
        while self.index < len(self.m5) and self.m5[self.index].t+300 <= end:
            m = self.m5[self.index]
            if m.t+300 == end and not gap: self.new_impulse(m)
            self.history.append(m); self.index += 1
        self.last_m1 = b.t; c = self.candidate
        if not c or c.state not in ('FORMING', 'TRIGGERED') or b.t < c.born: return
        if b.t >= c.expires or (c.state == 'FORMING' and end >= c.expires):
            self.close_candidate(end, 'EXPIRED', 'FORMING_EXPIRED'); return
        if c.state == 'TRIGGERED':
            if b.t >= c.entry_expires:
                self.close_candidate(end, 'EXPIRED', 'ENTRY_EXPIRED'); return
            entry, stop = decimal(c.plan['entry']), decimal(c.plan['stop'])
            et = b.l <= entry if c.direction == 'long' else b.h >= entry
            st = b.l <= max(stop, c.invalidation) if c.direction == 'long' else b.h >= min(stop, c.invalidation)
            if et and st: self.close_candidate(end, 'MISSED', 'AMBIGUOUS_TOUCH')
            elif st: self.close_candidate(end, 'INVALIDATED', 'STOP_BEFORE_ENTRY')
            elif et: self.close_candidate(end, 'MISSED', 'ENTRY_TOUCHED')
            elif end >= c.entry_expires: self.close_candidate(end, 'EXPIRED', 'ENTRY_EXPIRED')
            return
        invalid = b.l <= c.invalidation if c.direction == 'long' else b.h >= c.invalidation
        if invalid:
            self.close_candidate(end, 'INVALIDATED', 'TREND_INVALIDATED'); return
        overlap = b.l <= c.hi and b.h >= c.lo
        targets = self.target_levels(c)
        if overlap or c.touched:
            if not c.touched:
                c.touched = True
                self.event(end, 'PULLBACK_TOUCH', next_trigger='completed M1 rejection at frozen zone')
            value = b.l if c.direction == 'long' else b.h
            c.pullback_extreme = value if c.pullback_extreme is None else (
                min(c.pullback_extreme, value) if c.direction == 'long' else max(c.pullback_extreme, value))
            if rejection(b, c.direction, c.lo, c.hi):
                c.plan, c.reasons = structural_plan(c.direction, c, targets)
                c.trigger_end = end; c.entry_expires = min(end+120, c.expires); c.state = 'TRIGGERED'
                complete = self.context_complete()
                self.event(end, 'TRIGGERED', trigger_open=iso(b.t), entry_expires=iso(c.entry_expires),
                    geometry_pass=not c.reasons, execution_state='UNVERIFIED', context_screen_complete=complete,
                    execution_reasons=['COST_UNKNOWN', 'METADATA_MISSING']+([] if complete else ['HTF_SCREEN_INCOMPLETE']))
                if c.reasons:
                    c.state = 'REJECTED'; self.event(end, 'REJECTED')
                return
        if c.direction == 'long' and b.h > c.impulse_extreme: c.impulse_extreme, c.impulse_anchor = b.h, b.t
        if c.direction == 'short' and b.l < c.impulse_extreme: c.impulse_extreme, c.impulse_anchor = b.l, b.t

    def run(self, m1):
        for value in bars(m1, 60): self.step_bar(value)
        return {'version': VERSION, 'symbol': self.symbol, 'parameters': {
            'tolerance': str(self.tolerance), 'research_price_step': str(self.step), 'min_gross_rr': '2',
            'forming_seconds': 1800, 'pending_bars': 2, 'm5_lookback': 72,
            'entry_semantics': 'post_rejection_limit_retest_at_zone_edge'},
            'events': self.events, 'diagnostics': self.diagnostics,
            'current_candidate': None if self.candidate is None else {
                'id': self.candidate.id, 'setup_state': self.candidate.state, 'direction': self.candidate.direction,
                'zone': [str(self.candidate.lo), str(self.candidate.hi)],
                'invalidation': str(self.candidate.invalidation), 'plan': self.candidate.plan,
                'reason_codes': self.candidate.reasons, 'pattern_expires': iso(self.candidate.expires),
                'entry_expires': None if self.candidate.entry_expires is None else iso(self.candidate.entry_expires)},
            'last_m1_close': None if self.last_m1 is None else iso(self.last_m1+60),
            'limitations': ['historical costs unknown', 'execution unverified',
                'context completeness recorded per trigger', 'events are not trades',
                'TPR-2 is a preregistered research variant; no performance claim']}


def from_snapshot(document, symbol):
    cutoff = epoch(document['cutoff']); x = document['symbols'][symbol]
    context = {tf: bars(x[tf]['completed'], seconds, cutoff) for tf, seconds in [('m15', 900), ('h1', 3600)]
               if tf in x and 'completed' in x[tf]}
    return Engine(symbol, bars(x['m5']['completed'], 300, cutoff), context=context).run(
        bars(x['m1']['completed'], 60, cutoff))
