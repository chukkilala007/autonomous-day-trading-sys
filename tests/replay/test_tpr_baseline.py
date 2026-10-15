import json
from pathlib import Path
import sys
import tempfile
import unittest
from trading_platform.strategies.tpr1.baseline import (Bar,Candidate,D,Engine,PARAMETERS,bars,cost_reasons,execution_check,
                 iso,persist_state,pivots,rejection,structural_plan)
from trading_platform.strategies.tpr1.baseline_replay import load_history

BASE=1704067200 # Monday 2024-01-01 00:00 UTC, aligned to M5

def bar(t,o,h,l,c):return Bar(t,*(D(str(v)) for v in (o,h,l,c)))

def fixture(short=False):
    mids=[100,101,104,102,101,102,103,106,104,103,104,105,108,106,105,106,107,110]
    m5=[bar(BASE+i*300,D(v)-D('.1'),D(v)+D('.4'),D(v)-D('.4'),D(v)+D('.1')) for i,v in enumerate(mids)]
    born=BASE+18*300
    start=bar(born-60,110,110.4,109.6,110.1)
    trigger=bar(born,108.6,108.95,108.3,108.9)
    if short:
        mirror=lambda b:Bar(b.t,D(200)-b.o,D(200)-b.l,D(200)-b.h,D(200)-b.c)
        return [mirror(b) for b in m5],[mirror(start),mirror(trigger)]
    return m5,[start,trigger]

def engine(m5,**kw):return Engine('XAUUSD',m5,tolerance='.1',price_step='.01',**kw)

class CausalPatternTests(unittest.TestCase):
    def test_pivot_needs_right_bars(self):
        m5,_=fixture()
        self.assertNotIn(m5[2],pivots(m5[:4])[0])
        self.assertIn(m5[2],pivots(m5[:5])[0])

    def test_long_trigger_and_geometry(self):
        m5,m1=fixture();r=engine(m5).run(m1)
        self.assertEqual([e['event'] for e in r['events']],['FORMING','PULLBACK_TOUCH','TRIGGERED'])
        e=r['events'][-1]
        self.assertTrue(e['geometry_pass'])
        self.assertEqual(e['plan']['entry'],'108.96')
        self.assertEqual(e['plan']['stop'],'108.28')
        self.assertEqual(D(e['plan']['reward']),D('1.44'))
        self.assertEqual(e['execution_state'],'UNVERIFIED')
        self.assertIn('HTF_SCREEN_INCOMPLETE',e['execution_reasons'])

    def test_short_mirrors_long(self):
        m5,m1=fixture(True);e=engine(m5).run(m1)['events'][-1]
        self.assertEqual(e['direction'],'short');self.assertTrue(e['geometry_pass'])
        self.assertEqual(D(e['plan']['entry']),D('91.04'))
        self.assertEqual(D(e['plan']['stop']),D('91.72'))

    def test_watchlist_has_null_geometry(self):
        m5,m1=fixture();r=engine(m5).run(m1[:1])
        self.assertEqual(r['current_candidate']['setup_state'],'FORMING')
        self.assertIsNone(r['current_candidate']['plan'])

    def test_entry_cannot_fill_in_trigger_bar(self):
        m5,m1=fixture();r=engine(m5).run(m1)
        self.assertFalse(any(e['setup_state']=='MISSED' for e in r['events']))
        touch=bar(m1[-1].t+60,108.85,109,108.7,108.9)
        r=engine(m5).run(m1+[touch])
        self.assertEqual(r['events'][-1]['reason_codes'],['ENTRY_TOUCHED'])

    def test_ambiguous_entry_and_stop_is_not_success(self):
        m5,m1=fixture();touch=bar(m1[-1].t+60,108.85,109,108.1,108.9)
        e=engine(m5).run(m1+[touch])['events'][-1]
        self.assertEqual(e['reason_codes'],['AMBIGUOUS_TOUCH'])
        self.assertEqual(e['setup_state'],'MISSED')

    def test_stop_before_entry(self):
        m5,m1=fixture();touch=bar(m1[-1].t+60,108.7,108.8,108.1,108.2)
        e=engine(m5).run(m1+[touch])['events'][-1]
        self.assertEqual(e['reason_codes'],['STOP_BEFORE_ENTRY'])

    def test_expire_after_three_subsequent_bars(self):
        m5,m1=fixture()
        tail=[bar(m1[-1].t+i*60,108.7,108.8,108.6,108.7) for i in (1,2,3)]
        e=engine(m5).run(m1+tail)['events'][-1]
        self.assertEqual(e['reason_codes'],['ENTRY_EXPIRED'])
        self.assertEqual(e['decision_time'],iso(m1[-1].t+240))

    def test_gap_blocks_unseen_entry(self):
        m5,m1=fixture();b=bar(m1[-1].t+120,108.7,108.8,108.6,108.7)
        e=engine(m5).run(m1+[b])['events'][-1]
        self.assertEqual(e['setup_state'],'DATA_UNAVAILABLE')
        self.assertEqual(e['reason_codes'],['DATA_GAP'])

    def test_trend_invalidated_before_trigger(self):
        m5,m1=fixture();b=bar(m1[-1].t,108,108.5,104,104.5)
        e=engine(m5).run([m1[0],b])['events'][-1]
        self.assertEqual(e['reason_codes'],['TREND_INVALIDATED'])

    def test_no_lookahead_when_future_appended(self):
        m5,m1=fixture()
        partial=engine(m5).run(m1)['events']
        future_m5=m5+[bar(m5[-1].t+300,110,113,109,112)]
        tail=[bar(m1[-1].t+i*60,109,110,108.5,109.5) for i in range(1,6)]
        full=engine(future_m5).run(m1+tail)['events']
        cutoff=iso(m1[-1].t+60)
        self.assertEqual(partial,[e for e in full if e['decision_time']<=cutoff])

    def test_broken_swing_retired_as_obstacle(self):
        m5,m1=fixture();e=engine(m5);e.run(m1[:1])
        levels=e.target_levels(e.candidate)
        self.assertNotIn(D('108.4'),[v['price'] for v in levels])
        self.assertIn(D('110.4'),[v['price'] for v in levels])

    def test_higher_timeframe_obstacle_requires_confirmation(self):
        m5,m1=fixture();e=engine(m5);e.run(m1[:1])
        # A completed M15 swing at 109.5 is nearer than the 110.4 impulse.
        start=BASE-4500
        context=[bar(start+i*900,108,hi,107,108) for i,hi in enumerate([109,109.1,109.5,109.2,109.1])]
        e.context={'m15':context}
        e.now=context[-1].t+899
        self.assertNotIn(D('109.5'),[v['price'] for v in e.target_levels(e.candidate)])
        e.now=context[-1].t+900
        self.assertIn(D('109.5'),[v['price'] for v in e.target_levels(e.candidate)])

    def test_no_target_is_explicit_rejection(self):
        _,m1=fixture()
        plan,reasons=structural_plan('long',m1[-1],D('108.3'),D('.01'),[])
        self.assertIsNone(plan);self.assertEqual(reasons,['NO_TARGET'])

    def test_nearest_target_not_farther_profitable_target(self):
        _,m1=fixture();plan,reasons=structural_plan('long',m1[-1],D('108.3'),D('.01'),[
            {'price':D('109.1'),'anchor':'near','kind':'swing'},
            {'price':D('112'),'anchor':'far','kind':'swing'}])
        self.assertEqual(plan['target_anchor'],'near');self.assertIn('INSUFFICIENT_RR',reasons)

    def test_forming_expiry(self):
        m5,m1=fixture();born=m1[-1].t
        tail=[bar(born+i*60,110,110.3,109.9,110.1) for i in range(31)]
        r=engine(m5).run([m1[0]]+tail)
        self.assertEqual(r['events'][-1]['reason_codes'],['FORMING_EXPIRED'])

    def test_unfinished_excluded_and_invalid_bars_rejected(self):
        _,m1=fixture();self.assertEqual(bars(m1,60,m1[-1].t),m1[:1])
        with self.assertRaises(ValueError):bars([m1[0],m1[0]],60)
        with self.assertRaises(ValueError):Bar.read({'timestamp':iso(BASE),'open':1,'high':0,'low':0,'close':1})

    def test_zero_range_cannot_trigger(self):
        b=bar(BASE,108.5,108.5,108.5,108.5)
        self.assertFalse(rejection(b,'long',D('108.3'),D('108.5')))

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.plan={'entry':'100','stop':'99','tp1':'102','risk':'1','reward':'2','gross_rr':'2','geometry_basis':'executable'}
        self.quote={'bid':'99.50','ask':'99.60','source_time':iso(BASE)}
        self.meta={'tick_size':'.01','actual_session_open':True,'price_basis':'bid',
                   'session_source_time':iso(BASE),'availability_asof':iso(BASE),'context_screen_complete':True,
                   'provenance':{'tick_size':'test provider','actual_session_open':'test provider','price_basis':'test provider'}}

    def test_complete_metadata_can_pass(self):
        self.assertTrue(execution_check(self.plan,self.quote,self.meta,BASE+2,available=True,direction='long')['entry_ready'])

    def test_missing_source_not_replaced_by_local_time(self):
        q=dict(self.quote,source_time=None,observation_end=iso(BASE))
        r=execution_check(self.plan,q,self.meta,BASE,available=True,direction='long')
        self.assertFalse(r['entry_ready']);self.assertIn('SOURCE_TIME_MISSING',r['reasons'])

    def test_stale_and_future_quotes_block(self):
        for now in [BASE+31,BASE-1]:
            self.assertIn('STALE_QUOTE',execution_check(self.plan,self.quote,self.meta,now,available=True,direction='long')['reasons'])

    def test_research_grid_not_real_tick(self):
        m=dict(self.meta,tick_size=None,digits=2,pip_size='.01')
        self.assertIn('PRICE_GRID',execution_check(self.plan,self.quote,m,BASE,available=True,direction='long')['reasons'])

    def test_cost_threshold_and_unknown_cost(self):
        self.assertEqual(cost_reasons(self.plan,D('.20')),[])
        self.assertIn('COST_STOP',cost_reasons(self.plan,D('.20001')))
        self.assertEqual(cost_reasons(self.plan,None),['COST_UNKNOWN'])

    def test_closed_session_and_already_crossed_entry(self):
        r=execution_check(self.plan,dict(self.quote,ask='100.01'),dict(self.meta,actual_session_open=False),BASE,available=True,direction='long')
        self.assertIn('SESSION_CLOSED',r['reasons']);self.assertIn('ENTRY_TOUCHED',r['reasons'])

    def test_unknown_basis_never_execution_verified(self):
        r=execution_check(dict(self.plan,geometry_basis='research_candle_reference'),self.quote,self.meta,BASE,available=True,direction='long')
        self.assertIn('PRICE_BASIS_UNKNOWN',r['reasons'])

    def test_fabricated_rr_and_stale_availability_rejected(self):
        bad=dict(self.plan,tp1='100.5')
        r=execution_check(bad,self.quote,dict(self.meta,availability_asof=iso(BASE-61)),BASE,available=True,direction='long')
        self.assertIn('INVALID_GEOMETRY',r['reasons'])
        self.assertIn('INSUFFICIENT_RR',r['reasons'])
        self.assertIn('AVAILABILITY_UNVERIFIED',r['reasons'])

    def test_no_current_session_or_context_blocks(self):
        r=execution_check(self.plan,self.quote,dict(self.meta,session_source_time=None,context_screen_complete=False),BASE,available=True,direction='long')
        self.assertIn('SESSION_STATE_STALE',r['reasons'])
        self.assertIn('HTF_SCREEN_INCOMPLETE',r['reasons'])

class PersistenceTests(unittest.TestCase):
    def test_repeated_scan_events_deduplicated(self):
        m5,m1=fixture();r=engine(m5).run(m1)
        with tempfile.TemporaryDirectory() as folder:
            p=persist_state(folder,r,iso(BASE));persist_state(folder,r,iso(BASE+60))
            saved=json.loads(p.read_text())
            self.assertEqual(saved['events'],sorted(r['events'],key=lambda e:(e['decision_time'],e['candidate_id'],e['event'])))
            self.assertEqual(saved['revisions'],[])

    def test_snapshot_overlaps_deduplicate_and_conflicts_fail(self):
        raw={'timestamp':iso(BASE),'open':1,'high':2,'low':0,'close':1}
        doc={'cutoff':iso(BASE+300),'symbols':{'EURUSD':{'m1':{'completed':[raw]},'m5':{'completed':[raw]}}}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ['one','two']:
                p=root/'2024-01-01'/name;p.mkdir(parents=True);(p/'data-snapshot.json').write_text(json.dumps(doc))
            data,_,_=load_history(root);self.assertEqual(len(data['EURUSD']['m1']),1)
            doc['symbols']['EURUSD']['m1']['completed'][0]['close']=1.5
            (root/'2024-01-01'/'two'/'data-snapshot.json').write_text(json.dumps(doc))
            with self.assertRaises(ValueError):load_history(root)

if __name__=='__main__':unittest.main()
