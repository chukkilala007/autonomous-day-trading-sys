from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal as D
import pytest
from trading_platform.persistence.database import Database
from trading_platform.contracts.config import AccountPolicy
from trading_platform.contracts.values import utc
from trading_platform.risk.reservations import RiskBook
T=utc('2024-10-27T00:30:00Z')

def test_concurrent_budget_and_persistent_limits(tmp_path):
    path=tmp_path/'db';policy=AccountPolicy(alias='paper',environment='paper')
    with Database(path) as db:
        b=RiskBook(db,policy);b.limits.observe(T,D(10000))
        def submit(n):
            try: return b.reserve(str(n),str(n),'X'+str(n),'B'+str(n),D(50),D(10000),D('.005'),T)
            except ValueError: return False
        with ThreadPoolExecutor(max_workers=3) as pool: assert sum(pool.map(submit,range(3)))==2
        with pytest.raises(ValueError):
            with db.transaction() as c: b.release_in(c,'0','UNKNOWN')
        # Deposit is not profit and withdrawal is not loss.
        assert not b.limits.observe(T,D(11000),D(1000))['daily_halt']
        assert b.limits.observe(T,D(10799),D(1000))['daily_halt']
    with Database(path) as db:
        b=RiskBook(db,policy)
        with pytest.raises(ValueError):
            with db.transaction() as c: b.limits.check(c,T)
        tomorrow=T+timedelta(days=1)
        b.limits.observe(tomorrow,D(10799),D(1000))
        with db.transaction() as c: b.limits.check(c,tomorrow)
        for n in range(3): b.limits.record_trade(str(n),D(-1),tomorrow)
        b.limits.record_trade('2',D(-1),tomorrow)
        with pytest.raises(ValueError):
            with db.transaction() as c: b.limits.check(c,tomorrow)
        with db.transaction() as c: b.limits.check(c,tomorrow+timedelta(hours=1))
