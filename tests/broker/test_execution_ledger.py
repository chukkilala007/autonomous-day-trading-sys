import json
from decimal import Decimal as D
from trading_platform.persistence.database import Database
from trading_platform.gateways.ctrader.execution import ExecutionLedger,close_net
from trading_platform.execution.protection import recovery_action


def test_fill_without_protection_latches_and_old_updates_do_not_regress(tmp_path):
    with Database(tmp_path/'db') as db:
        with db.transaction() as c: c.execute('INSERT INTO checkpoints VALUES (?,?)',('gateway-send:intent',json.dumps({'instance':'a','fields':{'clientOrderId':'c','symbolId':1,'volume':200,'tradeSide':1,'limitPrice':100,'stopLoss':99,'takeProfit':103},'status':'UNKNOWN'})))
        ledger=ExecutionLedger(db,12)
        event={'ctidTraderAccountId':'12','executionType':'ORDER_PARTIAL_FILL','order':{'orderId':'1','clientOrderId':'c','positionId':'2','tradeData':{'symbolId':'1','volume':'200','tradeSide':'BUY'},'limitPrice':100},'position':{'positionId':'2','tradeData':{'volume':'200'},'utcLastUpdateTimestamp':'100','positionStatus':'POSITION_STATUS_OPEN'}}
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


def test_cancelled_remainder_does_not_close_late_fill_and_requires_revision(tmp_path):
    from copy import deepcopy
    from datetime import datetime,timezone,timedelta
    from trading_platform.gateways.ctrader.management import prepare
    from trading_platform.contracts.orders import Management
    import pytest
    with Database(tmp_path/'db') as db:
        with db.transaction() as c:
            c.execute('INSERT INTO checkpoints VALUES (?,?)',('gateway-send:x',json.dumps({'instance':'a','fields':{'clientOrderId':'x','symbolId':1,'volume':500,'tradeSide':1,'limitPrice':100,'stopLoss':99},'status':'UNKNOWN'})))
        ledger=ExecutionLedger(db,12)
        order={'orderId':'1','clientOrderId':'x','positionId':'2','limitPrice':100,'utcLastUpdateTimestamp':'100','tradeData':{'symbolId':'1','volume':'500','tradeSide':'BUY'},'executedVolume':'200','orderStatus':'ORDER_STATUS_ACCEPTED'}
        event={'ctidTraderAccountId':'12','order':order}
        ledger.apply(event)
        now=datetime(2026,1,1,tzinfo=timezone.utc)
        cancel=Management(target_id='1',owner='a',revision=100,action='cancel',expires_at=now+timedelta(seconds=5))
        assert prepare(ledger,'a',cancel,now)==('ProtoOACancelOrderReq',{'orderId':1})
        assert ledger.owned_order(1,'a')['remaining']=='3'
        with pytest.raises(ValueError): prepare(ledger,'b',cancel,now)
        with pytest.raises(ValueError): prepare(ledger,'a',cancel.model_copy(update={'revision':99}),now)
        old=deepcopy(event)
        order.update(orderStatus='ORDER_STATUS_CANCELLED',utcLastUpdateTimestamp='102')
        ledger.apply(event)
        with pytest.raises(ValueError): prepare(ledger,'a',cancel,now)
        # Delayed partial-fill event retains exposure without reopening cancelled remainder.
        old['position']={'positionId':'2','utcLastUpdateTimestamp':'101','tradeData':{'volume':'200','tradeSide':'BUY'},'positionStatus':'POSITION_STATUS_OPEN','stopLoss':99}
        ledger.apply(old)
        assert ledger.owned(2,'a')['quantity']=='2'
        with pytest.raises(ValueError): ledger.owned_order(1,'a')
        restarted=ExecutionLedger(db,12)
        assert restarted.owned(2,'a')['protected']


def test_correlation_alone_cannot_adopt_foreign_order_or_position(tmp_path):
    import pytest
    with Database(tmp_path/'db') as db:
        fields={'clientOrderId':'collision','symbolId':1,'volume':200,'tradeSide':1,'limitPrice':100,'stopLoss':99}
        with db.transaction() as c:c.execute('INSERT INTO checkpoints VALUES (?,?)',('gateway-send:x',json.dumps({'instance':'a','fields':fields,'status':'UNKNOWN'})))
        event={'ctidTraderAccountId':'12','order':{'orderId':'3','clientOrderId':'collision','positionId':'4','tradeData':{'symbolId':'999','volume':'200','tradeSide':'BUY'},'limitPrice':100,'utcLastUpdateTimestamp':'100'},'position':{'positionId':'4','tradeData':{'volume':'200'},'utcLastUpdateTimestamp':'100','positionStatus':'POSITION_STATUS_OPEN'}}
        ledger=ExecutionLedger(db,12);ledger.apply(event)
        with pytest.raises(ValueError):ledger.owned(4,'a')
        assert json.loads(db.connection.execute("SELECT body FROM checkpoints WHERE id='gateway-send:x'").fetchone()[0])['status']=='UNKNOWN'
        event['order']['tradeData']['symbolId']='1';event['order']['positionId']='5'
        with pytest.raises(ValueError,match='binding'):ledger.apply(event)
