import socket,time
from pathlib import Path
from trading_platform.runtime.transport import request
TOKEN=Path('/run/secrets/worker_token').read_text().strip()
for _ in range(30):
    try:
        assert request('worker',9000,TOKEN,'test',{'op':'ping'})['healthy']
        break
    except OSError: time.sleep(.2)
else: raise AssertionError('worker never ready')
try: request('worker',9000,'bad','test',{'op':'ping'})
except ValueError: pass
else: raise AssertionError('unauthorized request accepted')
try: socket.create_connection(('gateway',9000),timeout=.2)
except OSError: pass
else: raise AssertionError('broker network reachable')
assert not Path('/state').exists()
assert not Path('/run/secrets/broker_token').exists()
print('Container authentication, broker-network isolation and secret/database isolation passed')
