from __future__ import annotations
import numpy as np
from typing import Dict, Tuple, List

def spread_bps(bb: float, ba: float, mid: float) -> float:
    if mid<=0 or ba<=0 or bb<=0: return 0.0
    return (ba-bb)/mid*1e4

def topn_imbalance(bids: List[Tuple[float,float]], asks: List[Tuple[float,float]], n:int=5)->float:
    b=sum(q for _,q in bids[:n]); a=sum(q for _,q in asks[:n]);
    return 0.0 if (a+b)==0 else (b-a)/(a+b)

def microprice_deviation(micro: float, mid: float)->float:
    return (micro-mid)/mid if mid>0 else 0.0

class ShortVolEWMA:
    def __init__(self, alpha: float=0.06)->None:
        self.alpha=alpha; self.var=0.0; self.last=None
    def update(self, price: float)->float:
        if self.last is None:
            self.last=price; return 0.0
        ret=(price-self.last)/self.last
        self.var=self.alpha*(ret**2) + (1-self.alpha)*self.var
        self.last=price
        return float(np.sqrt(self.var))

def order_flow_imbalance(prev_bids, prev_asks, bids, asks)->float:
    def best(x): return x[0] if x else (0.0,0.0)
    pbb,qbb=best(prev_bids); pba,qba=best(prev_asks)
    bb,qb=best(bids); ba,qa=best(asks)
    ofi=0.0
    if bb>pbb: ofi+=qb
    elif bb<pbb: ofi-=qbb
    if ba<pba: ofi+=qa
    elif ba>pba: ofi-=qba
    return ofi

def make_feature_row(bb,bq,ba,aq,bids,asks,prev_bids,prev_asks,vol_ewma,n=5)->Dict[str,float]:
    mid=(bb+ba)/2.0 if bb>0 and ba>0 else 0.0
    spr_bps=spread_bps(bb,ba,mid)
    imb=topn_imbalance(bids,asks,n)
    micro=(bb*aq + ba*bq)/(bq+aq) if (bq+aq)>0 else mid
    mp_dev=microprice_deviation(micro, mid)
    vol=vol_ewma.update(mid if mid>0 else (bb or ba))
    ofi=order_flow_imbalance(prev_bids, prev_asks, bids, asks)
    return {"mid":mid, "spread_bps":spr_bps, "imb":imb, "micro_dev":mp_dev, "vol":vol, "ofi":ofi}

def label_k_tick_ahead(mids: List[float], k:int, thresh_bps: float)->int:
    if not mids or len(mids)<=k: return 0
    m0=mids[0]
    up=max((m-m0)/m0*1e4 for m in mids[1:k+1])
    dn=min((m-m0)/m0*1e4 for m in mids[1:k+1])
    if up>thresh_bps: return 1
    if dn<-thresh_bps: return -1
    return 0
