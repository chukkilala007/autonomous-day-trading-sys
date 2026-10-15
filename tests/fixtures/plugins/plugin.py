class First:
    def initialize(self,instance): return '{}'
    def evaluate(self,*args): return None
    def validate_proposal(self,*args): return None
    def migrate_state(self,*args): raise ValueError('unsupported migration')
class Second(First): pass
