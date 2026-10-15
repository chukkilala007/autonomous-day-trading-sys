"""TPR-1 adapter. Execution conversion is explicit and paper-only until S5."""
import json
from decimal import Decimal as D
from datetime import timedelta
from .baseline import from_snapshot, execution_check, PARAMETERS
from trading_platform.contracts.values import canonical, utc
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.strategy import Evaluation


def baseline_snapshot(snapshot,symbol):
    periods={60:'m1',300:'m5',900:'m15',3600:'h1'}
    data={tf:{'completed':[]} for tf in periods.values()}
    for b in snapshot.bars:
        if b.instrument!=symbol: continue
        tf=periods.get(int((b.end-b.start).total_seconds()))
        if tf:
            data[tf]['completed'].append(dict(timestamp=b.start.isoformat(),open=str(b.open),high=str(b.high),low=str(b.low),close=str(b.close)))
    for series in data.values(): series['completed'].sort(key=lambda b:b['timestamp'])
    return {'cutoff':snapshot.cutoff.isoformat(),'symbols':{symbol:data}}


class TPR:
    def initialize(self,instance):
        if len(instance.universe)!=1 or instance.universe[0] not in PARAMETERS: raise ValueError('TPR universe')
        if json.loads(instance.parameters): raise ValueError('baseline parameters are fixed')
        return '{"emitted":[]}'

    def migrate_state(self,prior,state):
        if prior!='1': raise ValueError('unsupported state migration')
        return state

    def validate_proposal(self,proposal,snapshot):
        if proposal.kind!='entry': return
        risk=abs(proposal.worst_fill-proposal.stop)
        if proposal.target is None or abs(proposal.target-proposal.worst_fill)/risk<2:
            raise ValueError('TPR minimum reward/risk')

    def evaluate(self,instance,event,snapshot,portfolio,state):
        symbol=instance.universe[0]
        raw=from_snapshot(baseline_snapshot(snapshot,symbol),symbol)
        current=raw['current_candidate'];saved=json.loads(state)
        outcome='NO_ACTION';proposal=None;reasons=[]
        if not snapshot.coverage_complete:
            outcome='UNAVAILABLE';reasons=['DATA_GAP']
        elif current:
            outcome='WATCH';reasons=list(current['reason_codes'])
            if current['setup_state']=='TRIGGERED' and current['id'] not in saved['emitted']:
                triggers=[e for e in raw['events'] if e['event']=='TRIGGERED' and e['candidate_id']==current['id']]
                trigger=triggers[-1] if triggers else None
                quote=next((q for q in reversed(snapshot.quotes) if q.instrument==symbol),None)
                supplied=json.loads(event.payload).get('paper_execution',{})
                if instance.mode!='paper' or not supplied or quote is None:
                    reasons+=['EXECUTION_UNVERIFIED']
                elif trigger and trigger['geometry_pass'] and current['entry_expires'] and utc(current['entry_expires'])>snapshot.cutoff:
                    plan=dict(current['plan']);spread=quote.ask-quote.bid
                    # Reference BID candles: long entry uses ASK; short stop/target use ASK.
                    basis={b.basis for b in snapshot.bars if b.instrument==symbol}
                    if basis!={'bid'} or supplied.get('price_basis')!='bid':
                        reasons+=['PRICE_BASIS_UNKNOWN']
                    else:
                        direction=current['direction']
                        if direction=='long': plan['entry']=str(D(plan['entry'])+spread)
                        else:
                            plan['stop']=str(D(plan['stop'])+spread);plan['tp1']=str(D(plan['tp1'])+spread)
                        risk=abs(D(plan['entry'])-D(plan['stop']));reward=abs(D(plan['tp1'])-D(plan['entry']))
                        plan.update(risk=str(risk),reward=str(reward),gross_rr=str(reward/risk),geometry_basis='executable')
                        metadata=dict(supplied,context_screen_complete=trigger['context_screen_complete'],availability_asof=snapshot.cutoff.isoformat())
                        check=execution_check(plan,dict(bid=str(quote.bid),ask=str(quote.ask),source_time=quote.source_time.isoformat()),metadata,int(snapshot.cutoff.timestamp()),available=True,direction=direction)
                        reasons+=check['reasons']
                        if check['entry_ready']:
                            proposal=Entry(instrument=symbol,side='buy' if direction=='long' else 'sell',order_type='stop_limit',entry=plan['entry'],limit=plan['entry'],worst_fill=plan['entry'],stop=plan['stop'],target=plan['tp1'],expires_at=current['entry_expires'])
                            outcome='ENTRY';saved['emitted'].append(current['id'])
        d=Decision(instance=instance.instance_id,account=instance.account.alias,environment=instance.account.environment,package=instance.strategy,config_hash=instance.hash,event_id=event.event_id,snapshot_hash=snapshot.hash,at=snapshot.cutoff,outcome=outcome,proposal=proposal,reasons=tuple(reasons),diagnostics=canonical(raw))
        return Evaluation(state=canonical(saved),decisions=(d,))
