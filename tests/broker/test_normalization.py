from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
import pytest
from trading_platform.gateways.ctrader.normalization import relative_price, units, wire_volume, trendbar, spot
from trading_platform.gateways.ctrader.metadata import CapabilityReport, Evidence, REQUIRED
T=datetime(2026,1,1,tzinfo=timezone.utc)


def test_protocol_units_do_not_use_digits_or_lots():
    assert relative_price('123456')==D('1.23456')
    assert units('10001')==D('100.01') and wire_volume(D('100.01'))==10001
    for value in (True,1.5,'1.0','-1'):
        with pytest.raises(ValueError): units(value)
    with pytest.raises(ValueError): wire_volume(D('0.001'))


def test_finalized_bars_and_quote_freshness_are_explicit():
    raw=dict(utcTimestampInMinutes=str(int(T.timestamp()/60)),low='100000',deltaHigh='100',deltaOpen='20',deltaClose='80')
    with pytest.raises(ValueError): trendbar('X',raw,1,T,basis='bid')
    b=trendbar('X',raw,1,T+timedelta(minutes=1),basis='bid')
    assert b.close==D('1.0008') and b.high==D('1.001')
    with pytest.raises(ValueError): spot('X',{'bid':'100000','timestamp':str(int(T.timestamp()*1000))},T)


def test_synthetic_metadata_cannot_enable_execution():
    rows=tuple(Evidence(field=f,value='reviewed value',source='test',observed_at=T,valid_until=T+timedelta(seconds=30),classification='synthetic') for f in REQUIRED)
    report=CapabilityReport(account_id='12',symbol='X',evidence=rows)
    assert set(report.blockers(T,'12','X'))==REQUIRED
    verified=report.model_copy(update={'evidence':tuple(e.model_copy(update={'classification':'broker_verified'}) for e in rows)})
    assert verified.blockers(T,'12','X')==[]
    assert 'identity' in verified.blockers(T,'13','X')
    assert verified.blockers(T+timedelta(seconds=30),'12','X')
