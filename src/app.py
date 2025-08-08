from __future__ import annotations
import argparse, asyncio, time, yaml
from pydantic import BaseModel
from src.exchange.binance import BinanceExchange, ExchangeSettings, RateLimiter
from src.features.micro import ShortVolEWMA, make_feature_row
from src.model.online import OnlineSGD
from src.strategy.maker import StrategyParams, decide_entry
from src.exec.executor import Executor
from src.risk.risk import RiskManager, RiskLimits
from src.data.orderbook import L2Book
from src.utils.log import get_logger
class Settings(BaseModel):
    exchange: dict; symbols: list[str]; latency: dict; risk: dict; fees: dict; execution: dict; storage: dict
    model: dict; features: dict; logging: dict; rate_limit: dict; kill_switch: dict
async def run(symbol: str, mode: str)->None:
    import yaml
    with open("config/config.yaml","r") as f: cfg=Settings(**yaml.safe_load(f))
    logger=get_logger("app", path=cfg.logging["path"])
    ex=BinanceExchange(ExchangeSettings(mode=cfg.exchange["mode"], testnet=cfg.exchange["testnet"], base_url_spot=cfg.exchange["base_url_spot"], base_url_futures=cfg.exchange["base_url_futures"], ws_url_spot=cfg.exchange["ws_url_spot"], ws_url_futures=cfg.exchange["ws_url_futures"]), RateLimiter(1200,20), logger_path=cfg.logging["path"])
    await ex.init_symbol(symbol)
    risk=RiskManager(RiskLimits(cfg.risk["max_position"], cfg.risk["max_daily_loss_pct"], cfg.risk["max_orders_per_min"], cfg.risk["per_trade_notional"]), logger_path=cfg.logging["path"])
    params=StrategyParams(proba_threshold=cfg.model["proba_threshold"], timeout_ms=cfg.execution["order_timeout_ms"])
    execu=Executor(ex, params, cfg.execution["time_in_force"], cfg.execution["post_only"], cfg.execution["order_timeout_ms"], logger_path=cfg.logging["path"])
    book=L2Book(); vol=ShortVolEWMA(alpha=cfg.features["ewma_alpha"]); model=OnlineSGD(alpha=cfg.model["alpha"], eta0=cfg.model["eta0"], penalty=cfg.model["penalty"], random_state=cfg.model["random_state"])
    prev_bids=[]; prev_asks=[]; last_heartbeat=time.time()
    from binance.websocket.spot.websocket_client import SpotWebsocketClient
    ws=SpotWebsocketClient()
    def on_book(_, msg):
        nonlocal prev_bids, prev_asks
        bb=float(msg.get("b", msg.get("bestBid", 0.0)) or 0.0); bq=float(msg.get("B", msg.get("bestBidQty", 0.0)) or 0.0)
        ba=float(msg.get("a", msg.get("bestAsk", 0.0)) or 0.0); aq=float(msg.get("A", msg.get("bestAskQty", 0.0)) or 0.0)
        bids=[(bb,bq)]; asks=[(ba,aq)]; book.update_snapshot(bids, asks)
        feat=make_feature_row(bb,bq,ba,aq,bids,asks,prev_bids,prev_asks,vol,n=cfg.features["top_n_depth"]); prev_bids, prev_asks=bids, asks
        if not model.inited: model.partial_fit([feat],[0])
        prob_up=model.predict_proba_up(feat); decision=decide_entry(prob_up, feat["spread_bps"], feat["imb"], cfg.model["proba_threshold"])
        if risk.kill_switch(): ws.stop(); return
        if decision.side and risk.can_place_order():
            asyncio.create_task(execu.place_maker(symbol, decision.side, feat["mid"], max(1e-2, (book.spread() or 1e-2)/2.0), cfg.risk["per_trade_notional"])); risk.record_order()
    ws.start(); ws.book_ticker(symbol=symbol.lower(), id=101, callback=on_book)
    try:
        while True:
            await asyncio.sleep(cfg.latency["decision_ms"]/1000.0)
            for cid in list(execu.live_orders.keys()): await execu.cancel_if_timeout(cid)
            if time.time()-last_heartbeat > cfg.kill_switch["heartbeat_ms"]/1000.0:
                last_heartbeat=time.time(); logger.info("heartbeat", extra={"extra": {"ts": last_heartbeat}})
    finally: ws.stop()

def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument("--mode", default="testnet", choices=["testnet","paper","live"]); ap.add_argument("--symbol", required=True)
    args=ap.parse_args(); import asyncio; asyncio.run(run(args.symbol, args.mode))
if __name__=="__main__": main()
