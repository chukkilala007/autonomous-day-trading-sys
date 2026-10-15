"""Secret-file storage and exact demo-account binding. No secret logging."""
import json
import os
import tempfile
from pathlib import Path


class TokenStore:
    def __init__(self, seed, rotated):
        self.seed, self.rotated = Path(seed), Path(rotated)

    def read(self):
        path = self.rotated if self.rotated.exists() else self.seed
        if path.stat().st_mode & 0o077:
            raise ValueError('credential file must be private (0600)')
        value = json.loads(path.read_text())
        for field in ('client_id', 'client_secret', 'access_token', 'refresh_token', 'expires_at'):
            if field not in value: raise ValueError('incomplete credential file')
        if any(not isinstance(value[k], str) or not value[k] for k in ('client_id','client_secret','access_token','refresh_token')):
            raise ValueError('invalid credentials')
        if type(value['expires_at']) not in (int, float): raise ValueError('invalid token expiry')
        return value

    def rotate(self, original, response, now):
        if not response.get('accessToken') or not response.get('refreshToken') or int(response.get('expiresIn',0)) <= 0:
            raise ValueError('invalid refresh response')
        value = dict(original, access_token=response['accessToken'], refresh_token=response['refreshToken'], expires_at=now+int(response['expiresIn']))
        self.rotated.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(dir=self.rotated.parent)
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump(value, output); output.flush(); os.fsync(output.fileno())
            os.replace(name, self.rotated)
            directory = os.open(self.rotated.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(name): os.unlink(name)
        return value


def bind_demo(accounts, account_id):
    matches = [a for a in accounts if str(a.get('ctidTraderAccountId')) == str(account_id)]
    if len(matches) != 1 or matches[0].get('isLive') is not False:
        raise ValueError('explicit authorized demo account required')
    return matches[0]
