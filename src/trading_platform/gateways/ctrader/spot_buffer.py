"""Opt-in causal holding queue for the read-only spot collector.

Source timestamps are never rewritten. The strict stream validator still runs
at release. Pending queues block snapshots, including quotes accepted earlier.
"""
from collections import Counter,deque
from datetime import timedelta
from .normalization import timestamp_ms,relative_price


class SpotBuffer:
    MAX_LEAD=timedelta(milliseconds=100)
    MAX_RESIDENCE=0.250
    MAX_PENDING=64

    def __init__(self,stream,scheduler,monotonic):
        self.stream=stream;self.scheduler=scheduler;self.monotonic=monotonic
        self.pending={};self.stats=Counter()
        stream.on_disconnect=self.reset
        # Persisted pending flags must never make an old quote usable on restart.
        for symbol in stream.symbols:
            stream.feed.invalidate_quote(symbol)
            self._flag(symbol,False)

    def _flag(self,symbol,pending):
        self.stream.feed.put('quote-buffer-pending:'+symbol,{'pending':pending})

    def _drop(self,symbol,reason,extra=0):
        state=self.pending.pop(symbol,None)
        count=extra
        if state:
            count+=len(state['queue'])
            call=state.get('call')
            if call is not None and call.active():call.cancel()
        self.stats['dropped']+=count
        self.stats[reason]+=count
        self.stream.reject_spot(symbol,reason)
        self._flag(symbol,False)

    def reset(self):
        for symbol in tuple(self.pending):self._drop(symbol,'BUFFER_RESET')

    def on_spot(self,raw):
        stream=self.stream
        if str(raw.get('ctidTraderAccountId'))!=str(stream.session.account_id):
            raise ValueError('foreign account feed')
        symbol=next((s for s,sid in stream.symbols.items() if str(sid)==str(raw.get('symbolId'))),None)
        if symbol is None:raise ValueError('unknown symbol')
        try:
            at=timestamp_ms(raw['timestamp'])
            if not any(side in raw for side in ('bid','ask')):raise ValueError('missing side')
            for side in ('bid','ask'):
                if side in raw:relative_price(raw[side])
        except (KeyError,ValueError,TypeError):
            self._drop(symbol,'BUFFER_INVALID_SPOT',extra=1);return
        now=stream.now();state=self.pending.get(symbol)
        if at-now>self.MAX_LEAD:
            self._drop(symbol,'BUFFER_EXCESSIVE_SKEW',extra=1);return
        if not stream.session.ready:
            self._drop(symbol,'BUFFER_NOT_READY',extra=1);return
        if state and state['generation']!=stream.session.generation:
            self._drop(symbol,'BUFFER_GENERATION_CHANGE',extra=1);return
        if state and at<state['queue'][-1][0]:
            self._drop(symbol,'BUFFER_OUT_OF_ORDER',extra=1);return
        if state and len(state['queue'])>=self.MAX_PENDING:
            self._drop(symbol,'BUFFER_OVERFLOW',extra=1);return
        if state is None and at<=now:
            stream.on_spot(raw);return
        if state is None:
            self._flag(symbol,True)
            state={'queue':deque(),'generation':stream.session.generation,'call':None}
            self.pending[symbol]=state
        payload={key:raw[key] for key in ('ctidTraderAccountId','symbolId','timestamp','bid','ask') if key in raw}
        state['queue'].append((at,self.monotonic()+self.MAX_RESIDENCE,payload))
        self.stats['buffered']+=1
        self.stats['peak_pending']=max(self.stats['peak_pending'],len(state['queue']))
        if state['call'] is None:self._schedule(symbol,state)

    def _schedule(self,symbol,state):
        at,deadline,_=state['queue'][0]
        delay=min(max(0.001,(at-self.stream.now()).total_seconds()),
                  max(0,deadline-self.monotonic()))
        state['call']=self.scheduler.callLater(delay,self._flush,symbol,state)

    def _flush(self,symbol,state):
        if self.pending.get(symbol) is not state:return
        state['call']=None
        stream=self.stream
        if not stream.session.ready or stream.session.generation!=state['generation']:
            self._drop(symbol,'BUFFER_GENERATION_CHANGE');return
        while state['queue']:
            at,deadline,raw=state['queue'][0]
            if self.monotonic()>=deadline:
                self._drop(symbol,'BUFFER_EXPIRED');return
            if at>stream.now():
                self._schedule(symbol,state);return
            state['queue'].popleft()
            if not stream.on_spot(raw):
                self.stats['dropped']+=1
                self._drop(symbol,'BUFFER_RELEASE_REJECTED');return
            self.stats['released']+=1
        self.pending.pop(symbol)
        self._flag(symbol,False)

    def report(self):
        return dict(enabled=True,max_lead_ms=100,max_residence_ms=250,max_pending=64,
                    pending=sum(len(s['queue']) for s in self.pending.values()),counts=dict(self.stats))


def configured_buffer(stream, scheduler, monotonic, milliseconds=0):
    """Explicit opt-in only; callers cannot widen the reviewed causal bound."""
    if type(milliseconds) is not int or milliseconds not in (0, 100):
        raise ValueError('quote buffer must be 0 or 100 milliseconds')
    return SpotBuffer(stream, scheduler, monotonic) if milliseconds else None
