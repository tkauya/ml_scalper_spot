from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
@dataclass
class StrategyParams:
    proba_threshold: float=0.6
    target_bps: float=2.0
    stop_bps: float=3.0
    timeout_ms: int=2000
@dataclass
class SignalDecision:
    side: Optional[str]; reason: str

def decide_entry(prob_up: float, spread_bps: float, imb: float, proba_threshold: float)->SignalDecision:
    if spread_bps<=0.0: return SignalDecision(None, "no_spread")
    if prob_up>proba_threshold and imb>0: return SignalDecision("BUY", "up_prob_and_imbalance")
    if (1.0-prob_up)>proba_threshold and imb<0: return SignalDecision("SELL", "down_prob_and_imbalance")
    return SignalDecision(None, "no_edge")

def bps_to_price_delta(mid: float, bps: float)->float:
    return mid*(bps/1e4)
