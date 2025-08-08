from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple
@dataclass
class L2Book:
    bids: List[Tuple[float,float]] = field(default_factory=list)
    asks: List[Tuple[float,float]] = field(default_factory=list)
    def update_snapshot(self, bids, asks):
        self.bids=sorted([(p,q) for p,q in bids if q>0], key=lambda x:x[0], reverse=True)
        self.asks=sorted([(p,q) for p,q in asks if q>0], key=lambda x:x[0])
    def best_bid(self): return self.bids[0] if self.bids else (0.0,0.0)
    def best_ask(self): return self.asks[0] if self.asks else (0.0,0.0)
    def mid(self)->float:
        bb,_=self.best_bid(); ba,_=self.best_ask(); return 0.0 if bb==0.0 or ba==0.0 else (bb+ba)/2.0
    def spread(self)->float:
        bb,_=self.best_bid(); ba,_=self.best_ask(); return max(0.0, ba-bb)
    def microprice(self)->float:
        bb,bq=self.best_bid(); ba,aq=self.best_ask();
        if bb==0.0 or ba==0.0 or (bq+aq)==0.0: return self.mid()
        return (bb*aq + ba*bq)/(bq+aq)
