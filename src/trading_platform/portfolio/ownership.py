import json

TERMINAL=('CLOSED','CANCELLED','EXPIRED','REJECTED')


class Portfolio:
    def __init__(self,db): self.db=db

    def owner(self,target):
        c=self.db.connection
        row=c.execute('SELECT instance FROM commands WHERE id=?',(target,)).fetchone()
        if not row: row=c.execute('SELECT instance FROM positions WHERE id=?',(target,)).fetchone()
        if not row: raise ValueError('unknown target')
        return row['instance']

    def assert_owned(self,target,instance):
        if self.owner(target)!=instance: raise ValueError('unowned target')

    def symbol_available(self,instrument):
        c=self.db.connection
        return not (c.execute("SELECT 1 FROM commands WHERE instrument=? AND status NOT IN ('CLOSED','CANCELLED','EXPIRED','REJECTED')",(instrument,)).fetchone() or c.execute('SELECT 1 FROM positions WHERE instrument=?',(instrument,)).fetchone() or c.execute("SELECT 1 FROM reservations WHERE instrument=? AND status!='RELEASED'",(instrument,)).fetchone())

    def positions(self,instance):
        return tuple(json.loads(row['body']) for row in self.db.connection.execute('SELECT body FROM positions WHERE instance=?',(instance,)))
