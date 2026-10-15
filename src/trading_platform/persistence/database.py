"""Single-host single-writer SQLite with transactional migration and backup."""
import fcntl
import sqlite3
from pathlib import Path
from contextlib import contextmanager

SCHEMA = '''
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots(hash TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS instances(id TEXT PRIMARY KEY, package TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}', cursor INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'BOOTING', halt TEXT);
CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, instance TEXT NOT NULL, event_seq INTEGER NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY, old_hash TEXT NOT NULL, new_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY, instance TEXT NOT NULL, instrument TEXT NOT NULL, bucket TEXT NOT NULL, amount TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, instance TEXT NOT NULL, instrument TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, command TEXT NOT NULL, at TEXT NOT NULL, outcome TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS broker_events(id TEXT PRIMARY KEY, command TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS positions(id TEXT PRIMARY KEY, instance TEXT NOT NULL, instrument TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkpoints(id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS halts(id TEXT PRIMARY KEY, reason TEXT NOT NULL);
'''


class Database:
    def __init__(self, path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=open(str(path)+'.lock','a+')
        try: fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close();raise ValueError('another database writer is active')
        self.connection=sqlite3.connect(path,isolation_level=None)
        self.connection.row_factory=sqlite3.Row
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.execute('PRAGMA foreign_keys=ON')
        try:
            version=self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version>1: raise ValueError('unsupported future schema')
            with self.transaction() as c:
                for statement in SCHEMA.split(';'):
                    if statement.strip(): c.execute(statement)
                c.execute('PRAGMA user_version=1')
        except Exception:
            self.close();raise

    @contextmanager
    def transaction(self):
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield self.connection
            self.connection.execute('COMMIT')
        except BaseException:
            self.connection.execute('ROLLBACK');raise

    def backup(self,path):
        with sqlite3.connect(path) as target: self.connection.backup(target)

    def close(self):
        self.connection.close();self.lock.close()

    def __enter__(self): return self
    def __exit__(self,*args): self.close()
