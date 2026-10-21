"""Durable bounded-test rehearsal. Deliberately has no broker/client/enable path.

Actions are simulation instructions, never executable outbox commands. A future
attended adapter must supply reviewed evidence and preserve the existing gates.
"""
import json
from decimal import Decimal
from typing import Literal
from pydantic import model_validator
from trading_platform.contracts.values import Record, Name, Positive, Time, canonical, digest, utc
from trading_platform.contracts.orders import Entry


class Plan(Record):
    test_id: Name
    account_id: Name
    entry: Entry
    quantity: Positive
    equity: Positive
    planned_loss: Positive
    created_at: Time
    mode: Literal['offline_rehearsal'] = 'offline_rehearsal'

    @model_validator(mode='after')
    def bounds(self):
        e = self.entry
        if e.instrument != 'EURUSD' or e.side != 'buy' or e.order_type != 'limit' or e.target is None:
            raise ValueError('EURUSD protected BUY LIMIT only')
        if not e.stop < e.entry < e.target or self.quantity != 1000:
            raise ValueError('test quantity/protection bounds')
        if self.planned_loss > min(Decimal('5'), self.equity * Decimal('0.001')):
            raise ValueError('test loss ceiling')
        if (e.expires_at - self.created_at).total_seconds() != 60:
            raise ValueError('exact 60-second rehearsal expiry required')
        return self


class Exposure(Record):
    id: Name
    owner: Name
    quantity: Positive
    protected: bool = False


class Observation(Record):
    account_id: Name
    observed_at: Time
    connected: bool
    history_complete: bool
    external_exposure: bool
    pending: tuple[Exposure, ...] = ()
    positions: tuple[Exposure, ...] = ()
    submission_terminal: bool = False
    settlement_complete: bool = False
    # A deterministic fixture is not a broker observation.
    source: Literal['deterministic_transport'] = 'deterministic_transport'


class Controller:
    def __init__(self, db, plan):
        self.db = db
        self.plan = Plan.model_validate_json(plan.model_dump_json())
        self.key = 'bounded-rehearsal:' + plan.test_id
        with db.transaction() as c:
            row = c.execute('SELECT body FROM checkpoints WHERE id=?', (self.key,)).fetchone()
            if row:
                if json.loads(row['body'])['plan_hash'] != digest(self.plan):
                    raise ValueError('cannot replace a started test plan')
            else:
                state = dict(plan_hash=digest(self.plan), status='PREPARED', journal=[], last_at=None)
                c.execute('INSERT INTO checkpoints VALUES (?,?)', (self.key, canonical(state)))

    def step(self, observation, now):
        observation = Observation.model_validate_json(observation.model_dump_json())
        now = utc(now)
        if observation.account_id != self.plan.account_id:
            raise ValueError('foreign account observation')
        owned = (*observation.pending, *observation.positions)
        if any(e.owner != self.plan.test_id for e in owned):
            raise ValueError('foreign exposure cannot be managed')
        if (len({e.id for e in observation.pending}) != len(observation.pending)
                or len({e.id for e in observation.positions}) != len(observation.positions)):
            raise ValueError('duplicate exposure identity')
        with self.db.transaction() as c:
            state = json.loads(c.execute('SELECT body FROM checkpoints WHERE id=?', (self.key,)).fetchone()['body'])
            actions = []

            def emit(kind, target=None):
                key = kind + ':' + (target or self.plan.test_id)
                if any(row['key'] == key for row in state['journal']):
                    return
                action = dict(key=key, action=kind, target=target, at=now.isoformat(),
                              executable=False, status='UNKNOWN_UNTIL_RECONCILED')
                state['journal'].append(action)
                actions.append(action)

            age = (now - observation.observed_at).total_seconds()
            elapsed = (now - self.plan.created_at).total_seconds()
            if state['status'] == 'COMPLETE' and owned:
                state['status'] = 'POST_COMPLETION_EXPOSURE_HALT'
            elif state['status'] in ('COMPLETE', 'ABORTED', 'CLOCK_HALTED', 'POST_COMPLETION_EXPOSURE_HALT'):
                pass
            elif state['last_at'] and now < utc(state['last_at']):
                state['status'] = 'CLOCK_HALTED'
            elif not observation.connected or not observation.history_complete or not 0 <= age <= 2:
                state['status'] = 'RECONCILIATION_REQUIRED'
            elif observation.external_exposure:
                state['status'] = 'EXTERNAL_EXPOSURE_HALT'
            elif not state['journal']:
                if owned or not 0 <= elapsed <= 2:
                    state['status'] = 'ABORTED'
                else:
                    emit('SUBMIT_ONCE')
                    state['status'] = 'AWAITING_BROKER_EVIDENCE'
            elif sum(e.quantity for e in owned) > self.plan.quantity:
                state['status'] = 'EXPOSURE_BOUND_BREACH'
            else:
                # Partial fills still require cancelling the remaining owned order.
                for order in observation.pending:
                    if elapsed >= 20 or observation.positions:
                        emit('CANCEL_OWNED', order.id)
                for position in observation.positions:
                    if not position.protected or elapsed >= 120:
                        emit('CLOSE_OWNED', position.id)
                if not owned and observation.submission_terminal and observation.settlement_complete:
                    state['status'] = 'COMPLETE'
                elif not owned:
                    state['status'] = 'AWAITING_TERMINAL_SETTLEMENT'
                elif elapsed >= 120:
                    state['status'] = 'CLEANUP_UNCONFIRMED'
                elif elapsed >= 60:
                    state['status'] = 'EXPIRY_UNCONFIRMED'
                else:
                    state['status'] = 'MONITORING'
            state['last_at'] = now.isoformat()
            c.execute('UPDATE checkpoints SET body=? WHERE id=?', (canonical(state), self.key))
        return dict(status=state['status'], actions=actions, orders_enabled=False,
                    mode='offline_rehearsal', journal_hash=digest(state['journal']))
