import pytest
from trading_platform.persistence.database import Database
from trading_platform.portfolio.ownership import Portfolio
from trading_platform.portfolio.arbiter import external_risk,arbitrate
from types import SimpleNamespace


def test_ownership_and_conflict(tmp_path):
    with Database(tmp_path/'db') as db:
        p=Portfolio(db)
        assert p.symbol_available('X')
        db.connection.execute("INSERT INTO commands(id,instance,instrument,body,status) VALUES ('c','a','X','{}','UNKNOWN')")
        assert not p.symbol_available('X')
        with pytest.raises(ValueError): p.assert_owned('c','b')
        p.assert_owned('c','a')
        db.connection.execute("UPDATE commands SET status='CLOSED'")
        assert p.symbol_available('X')

def test_arbitration_and_unknown_exposure():
    a=SimpleNamespace(instance='a',at=1,id='2');b=SimpleNamespace(instance='b',at=1,id='1')
    assert arbitrate([a,b],{})==[b,a]
    assert arbitrate([a,b],{'a':0})==[a,b]
    with pytest.raises(ValueError): external_risk([{'verified':False,'risk':None}])
    assert external_risk([{'verified':True,'risk':'12.50'}])==12.5
