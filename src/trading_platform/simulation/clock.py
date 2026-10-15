from trading_platform.contracts.values import utc


class Clock:
    def __init__(self,at): self.now=utc(at)
    def advance(self,at):
        at=utc(at)
        if at<self.now: raise ValueError('clock cannot move backwards')
        self.now=at
