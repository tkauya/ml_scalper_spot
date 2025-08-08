from __future__ import annotations
import time
from dataclasses import dataclass
from src.utils.log import get_logger
@dataclass
class RiskLimits:
    max_pos: float; max_daily_loss_pct: float; max_orders_per_min: int; per_trade_notional: float
class RiskManager:
    def __init__(self, limits: RiskLimits, logger_path: str|None)->None:
        self.l=limits; self.logger=get_logger("risk", path=logger_path)
        self.pnl_day=0.0; self.equity_start=10000.0; self.last_min=int(time.time()//60); self.ord_count_min=0
    def heartbeat(self)->None:
        now_min=int(time.time()//60)
        if now_min!=self.last_min: self.ord_count_min=0; self.last_min=now_min
    def can_place_order(self)->bool:
        self.heartbeat()
        if self.ord_count_min>=self.l.max_orders_per_min:
            self.logger.info("ratelimit_block", extra={"extra": {"orders_min": self.ord_count_min}}); return False
        return True
    def record_order(self)->None: self.ord_count_min+=1
    def kill_switch(self)->bool:
        dd=-min(0.0, self.pnl_day)/self.equity_start*100.0
        if dd>self.l.max_daily_loss_pct:
            self.logger.info("kill_switch_trigger", extra={"extra": {"dd_pct": dd}}); return True
        return False
    def record_pnl(self, pnl: float)->None:
        self.pnl_day+=pnl; self.logger.info("pnl_update", extra={"extra": {"pnl_day": self.pnl_day}})
