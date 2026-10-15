"""Generate a fully synthetic two-strategy paper scenario; no market claims."""
import json,runpy
from pathlib import Path
from datetime import timedelta
from decimal import Decimal as D
from trading_platform.contracts.events import Event,Quote,Bar
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.values import canonical
from trading_platform.risk.sizing import Contract
root=Path(__file__).resolve().parents[1]
s=runpy.run_path(str(root/'tests/replay/test_tpr_adapter.py'))['executable_snapshot']()
rows=[]
for n,seconds in enumerate((0,1,2,120)):
    at=s.cutoff+timedelta(seconds=seconds)
    prices=[('108.90','108.91'),('108.96','108.97'),('110.40','110.41'),('110.40','110.41')][n]
    quotes=(Quote(instrument='XAUUSD',bid=prices[0],ask=prices[1],source_time=at,received_at=at),Quote(instrument='TEST',bid='100',ask='100.01',source_time=at,received_at=at))
    bars=list(s.bars)
    if seconds==120:
        for k in range(2):
            start=s.cutoff+timedelta(seconds=60*k);end=start+timedelta(seconds=60)
            bars.append(Bar(instrument='XAUUSD',start=start,end=end,available_at=end,basis='bid',open='110.4',high='110.5',low='110.3',close='110.4'))
    snap=Snapshot(cutoff=at,bars=tuple(bars),quotes=quotes)
    metadata=dict(price_basis='bid',tick_size='0.01',actual_session_open=True,session_source_time=at.isoformat(),provenance={k:'synthetic-fixture' for k in ('price_basis','tick_size','actual_session_open')})
    event=Event(event_id=f'paper-{n}',kind='bar' if n==0 else ('timer' if n==3 else 'tick'),instrument='XAUUSD',source_time=at,available_at=at,payload=canonical({'paper_execution':metadata}))
    contracts={symbol:json.loads(Contract(instrument=symbol,account_currency='GBP',valuation_currency='GBP',quote_to_account='1',contract_value_per_unit='1',commission_per_unit='.01',slippage_per_unit='.01',minimum='1',maximum='100',step='1',tick='.01',margin_per_unit='1',verified_at=at,provenance='synthetic-fixture').model_dump_json()) for symbol in ('XAUUSD','TEST')}
    rows.append(dict(event=json.loads(event.model_dump_json()),snapshot=json.loads(snap.model_dump_json()),contracts=contracts))
(root/'tests/fixtures/paper.json').write_text(json.dumps(rows,indent=2)+'\n')
