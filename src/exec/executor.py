from __future__ import annotations
import time, uuid
from dataclasses import dataclass
from typing import Optional, Dict
from src.exchange.binance import BinanceExchange
from src.strategy.maker import StrategyParams, bps_to_price_delta
from src.utils.log import get_logger
@dataclass
class OrderState:
    client_id: str; symbol: str; side: str; price: float; qty: float; ts: float; active: bool=True
class Executor:
    def __init__(self, ex: BinanceExchange, params: StrategyParams, tif: str, post_only: bool, order_timeout_ms: int, logger_path: Optional[str])->None:
        self.ex=ex; self.params=params; self.tif=tif; self.post_only=post_only; self.order_timeout_ms=order_timeout_ms
        self.logger=get_logger("exec", path=logger_path); self.live_orders: Dict[str, OrderState] = {}
    async def place_maker(self, symbol: str, side: str, mid: float, tick: float, notional: float)->Optional[OrderState]:
        price=self.ex.conform_price(symbol, mid - tick if side=="BUY" else mid + tick)
        qty=self.ex.conform_qty(symbol, max(self.ex.symbol_filters[symbol].min_qty, notional/max(price,1e-9)))
        if not self.ex.meets_notional(symbol, price, qty):
            self.logger.info("reject_min_notional", extra={"extra": {"symbol":symbol, "price":price, "qty":qty}}); return None
        import uuid
        cid=f"mm-{uuid.uuid4().hex[:12]}"
        await self.ex.place_order(symbol, side, "LIMIT_MAKER", price, qty, time_in_force=self.tif, post_only=self.post_only, new_client_order_id=cid)
        st=OrderState(cid, symbol, side, price, qty, ts=time.time()); self.live_orders[cid]=st; return st
    async def cancel_if_timeout(self, cid: str)->None:
        st=self.live_orders.get(cid); 
        if not st or not st.active: return
        if (time.time()-st.ts)*1000 >= self.order_timeout_ms:
            await self.ex.cancel_order(st.symbol, client_order_id=st.client_id); st.active=False
            self.logger.info("order_timeout_cancel", extra={"extra": {"cid":cid}})
    async def handle_exit(self, st: OrderState, mid: float)->None:
        tp=st.price + (bps_to_price_delta(mid, self.params.target_bps) if st.side=="BUY" else -bps_to_price_delta(mid, self.params.target_bps))
        sl=st.price - (bps_to_price_delta(mid, self.params.stop_bps) if st.side=="BUY" else -bps_to_price_delta(mid, self.params.stop_bps))
        self.logger.info("exit_targets", extra={"extra": {"cid":st.client_id, "tp":tp, "sl":sl}})
