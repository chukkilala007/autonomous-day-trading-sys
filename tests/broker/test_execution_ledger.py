import json
from decimal import Decimal as D
from trading_platform.persistence.database import Database
from trading_platform.gateways.ctrader.execution import ExecutionLedger,close_net
from trading_platform.execution.protection import recovery_action


def test_fill_without_protection_latches_and_old_updates_do_not_regress(tmp_path):
    with Database(tmp_path/'db') as db:
        with db.transaction() as c: c.execute('INSERT INTO checkpoints VALUES (?,?)',('gateway-send:intent',json.dumps({'instance':'a','fields':{'clientOrderId':'c','stopLoss':99,'takeProfit':103},'status':'UNKNOWN'})))
        ledger=ExecutionLedger(db,12)
        event={'ctidTraderAccountId':'12','executionType':'ORDER_PARTIAL_FILL','order':{'orderId':'1','clientOrderId':'c'},'position':{'positionId':'2','tradeData':{'volume':'200'},'utcLastUpdateTimestamp':'100','positionStatus':'POSITION_STATUS_OPEN'}}
        assert ledger.apply(event) and not ledger.apply(event)
        assert not ledger.owned(2,'a')['protected']
        assert db.connection.execute('SELECT 1 FROM halts').fetchone()
        event['position'].update(stopLoss=99,takeProfit=103,utcLastUpdateTimestamp='101')
        ledger.apply(event);assert ledger.owned(2,'a')['protected']
        event['position'].update(stopLoss=90,utcLastUpdateTimestamp='99');ledger.apply(event)
        assert ledger.owned(2,'a')['record']['stopLoss']==99
        from trading_platform.gateways.ctrader.management import prepare
        from trading_platform.contracts.orders import Management
        from datetime import datetime,timezone,timedelta
        import pytest
        now=datetime(2026,1,1,tzinfo=timezone.utc)
        close=Management(target_id='2',owner='a',revision=101,action='close',expires_at=now+timedelta(seconds=5))
        name,fields=prepare(ledger,'a',close,now)
        assert name=='ProtoOAClosePositionReq' and fields['volume']==200
        with pytest.raises(ValueError): prepare(ledger,'other',close,now)
        with pytest.raises(ValueError): prepare(ledger,'a',close.model_copy(update={'revision':100}),now)
        # Protection confirmation does not silently clear the operational halt.
        assert db.connection.execute('SELECT 1 FROM halts').fetchone()


def test_unknown_costs_and_disconnected_recovery_are_explicit():
    assert close_net({}) is None
    assert close_net({'closePositionDetail':{'moneyDigits':2,'grossProfit':'1000','swap':'-10','commission':'-20','pnlConversionFee':'-5'}},signed_costs_verified=True)==D('9.65')
    assert recovery_action(owned=True,open_quantity=2,protected=False,connected=False,repair_attempted=True,repair_confirmed=False)=='HALT_UNABLE_TO_PROTECT_OR_CLOSE'
    assert recovery_action(owned=False,open_quantity=2,protected=False,connected=True,repair_attempted=False,repair_confirmed=False)=='OBSERVE_EXTERNAL'
