"""Deterministic bounded queues. Overflow requires explicit recovery/backfill."""
from collections import deque
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.strategy import Evaluation


class Scheduler:
    def __init__(self,capacity=100):
        if capacity<1: raise ValueError('queue capacity')
        self.capacity=capacity;self.queues={};self.blocked={};self.last={}

    def register(self,instance):
        if instance in self.queues: raise ValueError('duplicate queue')
        self.queues[instance]=deque()

    def enqueue(self,instance,event):
        if instance in self.blocked: raise ValueError(self.blocked[instance])
        q=self.queues[instance]
        if len(q)>=self.capacity:
            self.blocked[instance]='QUEUE_OVERFLOW_REQUIRES_BACKFILL'
            raise ValueError(self.blocked[instance])
        if instance in self.last and event.available_at<self.last[instance]:
            self.blocked[instance]='OUT_OF_ORDER_REQUIRES_REPLAY'
            raise ValueError(self.blocked[instance])
        q.append(event);self.last[instance]=event.available_at

    def pop(self,instance,cutoff):
        if instance in self.blocked: raise ValueError(self.blocked[instance])
        q=self.queues[instance]
        if not q or q[0].available_at>cutoff: return None
        return q.popleft()


def asof(cutoff,bars=(),quotes=(),features=(),coverage_complete=True):
    return Snapshot(cutoff=cutoff,
        bars=tuple(b for b in bars if b.available_at<=cutoff),
        quotes=tuple(q for q in quotes if q.received_at<=cutoff),
        features=tuple(f for f in features if f.available_at<=cutoff),
        coverage_complete=coverage_complete)


def evaluate(plugin,manifest,instance,event,snapshot,portfolio,state):
    if event.available_at>snapshot.cutoff: raise ValueError('event not available at cutoff')
    if not snapshot.coverage_complete: raise ValueError('DATA_GAP')
    if event.kind not in manifest.subscriptions: return Evaluation(state=state)
    return plugin.evaluate(instance,event,snapshot,portfolio,state)
