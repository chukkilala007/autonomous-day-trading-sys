"""Reactor-owned gateway lifecycle with an injected, audited provider adapter.

No credential loader or enabled broker launcher. The provider must return a
complete account-bound reconciliation plus a strict valuation observation.
"""
from twisted.internet import defer, task, threads
from ctrader_open_api import Protobuf
from google.protobuf.json_format import MessageToDict
from trading_platform.execution.recovery import DemoRecovery
from .valuation import export


class Lifecycle:
    def __init__(self, session, stream, ledger, provider, now):
        self.session=session; self.stream=stream; self.ledger=ledger
        self.provider=provider; self.now=now
        self.busy=False; self.stopped=False; self.observation=None
        self.generation=None; self.event_revision=0; self.reason='STARTUP_RECONCILIATION'
        self.drained=defer.succeed(None)

    def invalidate(self, reason):
        self.observation=None; self.reason=reason

    def valuation(self):
        if self.stopped or not self.session.ready or self.generation!=self.session.generation:
            self.invalidate('DISCONNECTED')
        if self.observation is None: raise ValueError(self.reason)
        return export(self.observation, self.session.account_id, self.now())

    def received(self, _client, message):
        try:
            payload=Protobuf.extract(message)
            name=payload.DESCRIPTOR.name
            if name=='ProtoOAExecutionEvent':
                self.event_revision+=1
                self.invalidate('EXECUTION_RECONCILIATION')
                self.ledger.apply(MessageToDict(payload,preserving_proto_field_name=True))
            elif name=='ProtoOASpotEvent':
                self.stream.on_spot(MessageToDict(payload,preserving_proto_field_name=True))
        except Exception:
            self.event_revision+=1
            self.invalidate('INVALID_PROVIDER_EVENT')
            self.stream.disconnected()

    @defer.inlineCallbacks
    def poll(self):
        if self.stopped or self.busy: return False
        if not self.session.ready:
            self.invalidate('DISCONNECTED'); self.stream.disconnected(); return False
        self.busy=True
        self.drained=defer.Deferred()
        generation=self.session.generation; revision=self.event_revision
        reconnect=generation!=self.generation
        self.invalidate('RECONCILING')
        try:
            yield self.session.refresh_if_due()
            yield self.stream.repair()
            # Provider collects history from the oldest unresolved local intent,
            # including opening costs; a fixed lookback is not completeness.
            bundle=yield self.provider.reconcile(reconnect=reconnect)
            if self.stopped or not self.session.ready or generation!=self.session.generation or revision!=self.event_revision:
                raise ValueError('session/event changed during collection')
            if str(bundle['account_id'])!=str(self.session.account_id) or bundle['history_complete'] is not True:
                raise ValueError('incomplete or foreign reconciliation')
            value=export(bundle['valuation'],self.session.account_id,self.now())
            if value['history_complete'] is not True: raise ValueError('incomplete valuation history')
            events=bundle['execution_events']
            if not isinstance(events,list): raise ValueError('execution events required')
            # Validate account identity before making any partial durable progress.
            if any(str(e.get('ctidTraderAccountId'))!=str(self.session.account_id) for e in events):
                raise ValueError('foreign historical execution')
            orders={}
            for event in events:
                order=event.get('order')
                if order:
                    key=str(order['orderId']); prior=orders.get(key)
                    if prior is None or int(order.get('utcLastUpdateTimestamp',0))>int(prior.get('utcLastUpdateTimestamp',0)):
                        orders[key]=order
            recovery=DemoRecovery(self.ledger.db,self.session.account_id)
            recovery.reconcile({'ctidTraderAccountId':str(self.session.account_id),'order':list(orders.values())},history_complete=True)
            for event in events: self.ledger.apply(event)
            self.observation=bundle['valuation']; self.generation=generation; self.reason=None
            return True
        except Exception:
            self.invalidate('RECONCILIATION_REQUIRED'); self.stream.disconnected(); return False
        finally:
            self.busy=False
            self.drained.callback(None)

    def stop(self):
        self.stopped=True; self.invalidate('STOPPED'); self.stream.disconnected()


class RunningGateway:
    """Own callbacks, polling and private RPC; stop RPC before closing storage.

    Construction does not start a connection. Caller supplies the account-bound
    controller/server and retains the explicit authorization gate.
    """
    def __init__(self, lifecycle, server, clock, interval=1):
        import threading
        if interval<=0: raise ValueError('positive polling interval required')
        self.lifecycle=lifecycle; self.server=server; self.clock=clock; self.interval=interval
        self.thread=threading.Thread(target=server.serve_forever,daemon=True)
        self.loop=task.LoopingCall(lifecycle.poll); self.loop.clock=clock
        self.started=False; self.stopping=None

    def start(self):
        if self.started or self.lifecycle.stopped: raise ValueError('gateway already started/stopped')
        self.started=True
        self.lifecycle.session.client.setMessageReceivedCallback(self.lifecycle.received)
        self.thread.start()
        self.loop.start(self.interval,now=False)
        self.lifecycle.session.client.startService()

    def stop(self):
        if self.stopping is None: self.stopping=self._stop()
        return self.stopping

    @defer.inlineCallbacks
    def _stop(self):
        self.lifecycle.stop()
        if self.loop.running: self.loop.stop()
        # Must not block the reactor: an RPC thread may be awaiting it.
        if self.started:
            yield threads.deferToThread(self.server.shutdown)
            yield threads.deferToThread(self.thread.join, 20)
            if self.thread.is_alive(): raise RuntimeError('RPC shutdown incomplete')
        self.server.server_close()
        yield defer.maybeDeferred(self.lifecycle.session.client.stopService)
        # Let in-flight collection settle before the owner can close storage.
        # Timeout fails shutdown explicitly and leaves storage owned/open.
        if self.lifecycle.busy:
            yield self.lifecycle.drained.addTimeout(20,self.clock)


def assemble(session, stream, ledger, provider, feed, reports, now, requirements,
             address, token, reactor):
    """Construct the operational graph with order authorization disabled.

    The caller owns the locked database and provider qualification. This factory
    is safe to exercise with a deterministic SDK transport; it never loads keys.
    """
    from .orders import DemoTransport
    from .demo_api import DemoAPI
    from .demo_server import reactor_server
    lifecycle=Lifecycle(session,stream,ledger,provider,now)
    gateway=DemoTransport(ledger.db,session,authorized=False)
    api=DemoAPI(gateway,ledger,feed,reports,lifecycle.valuation,now,requirements)
    server=reactor_server(address,token,api,reactor)
    service=RunningGateway(lifecycle,server,reactor)
    return service,api
