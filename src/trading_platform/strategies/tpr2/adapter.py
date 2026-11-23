"""TPR-2 adapter for replay/shadow and explicitly gated demo evaluation."""
import json
from decimal import Decimal as D

from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.strategy import Evaluation
from trading_platform.contracts.values import canonical, utc
from .baseline import PARAMETERS, execution_check, from_snapshot


def baseline_snapshot(snapshot, symbol):
    periods = {60: 'm1', 300: 'm5', 900: 'm15', 3600: 'h1'}
    data = {timeframe: {'completed': []} for timeframe in periods.values()}
    for bar in snapshot.bars:
        if bar.instrument != symbol: continue
        timeframe = periods.get(int((bar.end-bar.start).total_seconds()))
        if timeframe:
            data[timeframe]['completed'].append(dict(timestamp=bar.start.isoformat(), open=str(bar.open),
                high=str(bar.high), low=str(bar.low), close=str(bar.close)))
    for series in data.values(): series['completed'].sort(key=lambda bar: bar['timestamp'])
    return {'cutoff': snapshot.cutoff.isoformat(), 'symbols': {symbol: data}}


def limit_execution_check(plan, quote, metadata, now, *, direction):
    """Apply common evidence checks, replacing stop-entry touch with limit semantics."""
    checked = execution_check(plan, quote, metadata, now, available=True, direction=direction)
    reasons = [r for r in checked['reasons'] if r != 'ENTRY_TOUCHED']
    bid, ask, entry = D(str(quote['bid'])), D(str(quote['ask'])), D(plan['entry'])
    if (direction == 'long' and ask <= entry) or (direction == 'short' and bid >= entry):
        reasons.append('ENTRY_TOUCHED')
    reasons = list(dict.fromkeys(reasons))
    state = 'VERIFIED' if not reasons else 'UNVERIFIED'
    if any(r.startswith('COST_') and r != 'COST_UNKNOWN' for r in reasons): state = 'COST_FAIL'
    if 'STALE_QUOTE' in reasons: state = 'STALE'
    if 'SESSION_CLOSED' in reasons: state = 'CLOSED'
    return dict(checked, execution_state=state, entry_ready=not reasons, reasons=reasons)


class TPR2:
    def initialize(self, instance):
        if len(instance.universe) != 1 or instance.universe[0] not in PARAMETERS:
            raise ValueError('TPR-2 universe')
        if json.loads(instance.parameters): raise ValueError('TPR-2 parameters are fixed')
        if instance.mode == 'live': raise ValueError('TPR-2 is not live-qualified')
        return '{"emitted":[]}'

    def migrate_state(self, prior, state):
        if prior != '1': raise ValueError('unsupported state migration')
        return state

    def validate_proposal(self, proposal, snapshot):
        if proposal.kind != 'entry': return
        if proposal.order_type != 'limit': raise ValueError('TPR-2 requires limit entry')
        risk = abs(proposal.worst_fill-proposal.stop)
        if proposal.target is None or abs(proposal.target-proposal.worst_fill)/risk < 2:
            raise ValueError('TPR-2 minimum reward/risk')

    def evaluate(self, instance, event, snapshot, portfolio, state):
        symbol = instance.universe[0]
        raw = from_snapshot(baseline_snapshot(snapshot, symbol), symbol)
        current = raw['current_candidate']; saved = json.loads(state)
        outcome = 'NO_ACTION'; proposal = None; reasons = []
        if not snapshot.coverage_complete:
            outcome = 'UNAVAILABLE'; reasons = ['DATA_GAP']
        elif current:
            outcome = 'WATCH'; reasons = list(current['reason_codes'])
            if current['setup_state'] == 'TRIGGERED' and current['id'] not in saved['emitted']:
                triggers = [e for e in raw['events'] if e['event'] == 'TRIGGERED' and e['candidate_id'] == current['id']]
                trigger = triggers[-1] if triggers else None
                quote = next((q for q in reversed(snapshot.quotes) if q.instrument == symbol), None)
                supplied = json.loads(event.payload).get('execution_evidence', {})
                if not supplied or quote is None:
                    reasons += ['EXECUTION_UNVERIFIED']
                elif trigger and trigger['geometry_pass'] and current['entry_expires'] and utc(current['entry_expires']) > snapshot.cutoff:
                    plan = dict(current['plan']); spread = quote.ask-quote.bid
                    basis = {b.basis for b in snapshot.bars if b.instrument == symbol}
                    if basis != {'bid'} or supplied.get('price_basis') != 'bid':
                        reasons += ['PRICE_BASIS_UNKNOWN']
                    else:
                        direction = current['direction']
                        if direction == 'long': plan['entry'] = str(D(plan['entry'])+spread)
                        else:
                            plan['stop'] = str(D(plan['stop'])+spread)
                            plan['tp1'] = str(D(plan['tp1'])+spread)
                        risk = abs(D(plan['entry'])-D(plan['stop'])); reward = abs(D(plan['tp1'])-D(plan['entry']))
                        plan.update(risk=str(risk), reward=str(reward), gross_rr=str(reward/risk), geometry_basis='executable')
                        metadata = dict(supplied, context_screen_complete=trigger['context_screen_complete'],
                                        availability_asof=snapshot.cutoff.isoformat())
                        check = limit_execution_check(plan, dict(bid=str(quote.bid), ask=str(quote.ask),
                            source_time=quote.source_time.isoformat()), metadata, int(snapshot.cutoff.timestamp()), direction=direction)
                        reasons += check['reasons']
                        if check['entry_ready']:
                            proposal = Entry(instrument=symbol, side='buy' if direction == 'long' else 'sell',
                                order_type='limit', entry=plan['entry'], worst_fill=plan['entry'], stop=plan['stop'],
                                target=plan['tp1'], expires_at=current['entry_expires'])
                            outcome = 'ENTRY'; saved['emitted'].append(current['id'])
        decision = Decision(instance=instance.instance_id, account=instance.account.alias,
            environment=instance.account.environment, package=instance.strategy, config_hash=instance.hash,
            event_id=event.event_id, snapshot_hash=snapshot.hash, at=snapshot.cutoff, outcome=outcome,
            proposal=proposal, reasons=tuple(reasons), diagnostics=canonical(raw))
        return Evaluation(state=canonical(saved), decisions=(decision,))
