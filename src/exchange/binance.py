from __future__ import annotations
import asyncio, os, time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from binance.spot import Spot as SpotClient
from binance.websocket.spot.websocket_client import SpotWebsocketClient
from pydantic import BaseModel
from src.utils.log import get_logger
@dataclass
class SymbolFilters:
    price_tick: float; lot_step: float; min_qty: float; min_notional: float
class ExchangeSettings(BaseModel):
    mode: str; testnet: bool; base_url_spot: str; base_url_futures: str; ws_url_spot: str; ws_url_futures: str
class RateLimiter:
    def __init__(self, capacity_per_min: int, refill_per_sec: int) -> None:
        self.capacity=capacity_per_min; self.tokens=capacity_per_min; self.refill_per_sec=refill_per_sec; self.last=time.time(); self.lock=asyncio.Lock()
    async def acquire(self, tokens: int=1) -> None:
        async with self.lock:
            while self.tokens < tokens:
                now=time.time(); elapsed=now-self.last
                if elapsed>=1.0:
                    self.tokens=min(self.capacity, self.tokens+int(elapsed)*self.refill_per_sec); self.last=now
                await asyncio.sleep(0.01)
            self.tokens -= tokens
class BinanceExchange:
    def __init__(self, settings: ExchangeSettings, rl: RateLimiter, logger_path: Optional[str]) -> None:
        self.settings=settings; self.rl=rl; self.logger=get_logger("exchange", path=logger_path)
        api_key=os.getenv("BINANCE_API_KEY"); api_secret=os.getenv("BINANCE_API_SECRET")
        self.rest=SpotClient(base_url=settings.base_url_spot, key=api_key, secret=api_secret)
        self.ws_client=SpotWebsocketClient(); self.ws_url=settings.ws_url_spot
        self.symbol_filters: Dict[str, SymbolFilters] = {}
    async def init_symbol(self, symbol: str) -> None:
        await self.rl.acquire(); info=self.rest.exchange_info(symbol=symbol); f=info["symbols"][0]["filters"]
        price_tick=float([x for x in f if x["filterType"]=="PRICE_FILTER"][0]["tickSize"])
        lot_step=float([x for x in f if x["filterType"]=="LOT_SIZE"][0]["stepSize"])
        min_qty=float([x for x in f if x["filterType"]=="LOT_SIZE"][0]["minQty"])
        min_notional=float([x for x in f if x["filterType"] in ("MIN_NOTIONAL","NOTIONAL")][0]["minNotional"])
        self.symbol_filters[symbol]=SymbolFilters(price_tick, lot_step, min_qty, min_notional)
        self.logger.info("symbol_filters", extra={"extra": {"symbol": symbol, "filters": self.symbol_filters[symbol].__dict__}})
    def conform_price(self, symbol: str, price: float) -> float:
        tick=self.symbol_filters[symbol].price_tick; return round((price//tick)*tick, 8)
    def conform_qty(self, symbol: str, qty: float) -> float:
        step=self.symbol_filters[symbol].lot_step; return max(self.symbol_filters[symbol].min_qty, round((qty//step)*step, 8))
    def meets_notional(self, symbol: str, price: float, qty: float) -> bool:
        return price*qty >= self.symbol_filters[symbol].min_notional
    async def place_order(self, symbol: str, side: str, order_type: str, price: Optional[float], quantity: float,
                          time_in_force: str="GTC", post_only: bool=True, ioc: bool=False, fok: bool=False,
                          new_client_order_id: Optional[str]=None) -> Dict[str, Any]:
        await self.rl.acquire(); p={"symbol":symbol,"side":side.upper(),"type":order_type}
        if order_type in ("LIMIT","LIMIT_MAKER"):
            assert price is not None
            p.update({"price":f"{price:.8f}","quantity":f"{quantity:.8f}","timeInForce":"GTC" if not (ioc or fok) else ("IOC" if ioc else "FOK")})
            if order_type=="LIMIT_MAKER": p["type"]="LIMIT_MAKER"
        elif order_type=="MARKET": p.update({"quantity":f"{quantity:.8f}"})
        if new_client_order_id: p["newClientOrderId"]=new_client_order_id
        res=self.rest.new_order(**p); self.logger.info("order_placed", extra={"extra":{"params":p,"res":res}}); return res
    async def cancel_order(self, symbol: str, order_id: Optional[int]=None, client_order_id: Optional[str]=None) -> Dict[str, Any]:
        await self.rl.acquire(); res=self.rest.cancel_order(symbol=symbol, orderId=order_id, origClientOrderId=client_order_id)
        self.logger.info("order_canceled", extra={"extra": {"symbol":symbol, "order_id":order_id, "client_id":client_order_id, "res":res}}); return res
