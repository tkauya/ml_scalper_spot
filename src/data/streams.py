from __future__ import annotations
import argparse, asyncio, os, time
from typing import Any, Dict, List
import pandas as pd
from src.exchange.binance import BinanceExchange, ExchangeSettings, RateLimiter
from src.utils.log import get_logger
async def record(symbol: str, minutes: int, out_path: str, mode: str="spot", testnet: bool=True,
                 base_url_spot: str="", base_url_futures: str="", ws_url_spot: str="", ws_url_futures: str="") -> None:
    logger=get_logger("recorder")
    settings=ExchangeSettings(mode=mode, testnet=testnet, base_url_spot=base_url_spot,
                              base_url_futures=base_url_futures, ws_url_spot=ws_url_spot, ws_url_futures=ws_url_futures)
    rl=RateLimiter(capacity_per_min=1200, refill_per_sec=20); ex=BinanceExchange(settings, rl, logger_path=None)
    await ex.init_symbol(symbol)
    rows: List[Dict[str, Any]] = []; stop_ts=time.time()+60*minutes
    from binance.websocket.spot.websocket_client import SpotWebsocketClient
    ws=SpotWebsocketClient()
    def on_msg(_, msg: Dict[str, Any]) -> None:
        msg["ts_recv"]=int(time.time_ns()); rows.append(msg)
    ws.start(); ws.book_ticker(symbol=symbol.lower(), id=1, callback=on_msg)
    ws.diff_book_depth(symbol=symbol.lower(), id=2, speed=100, level=5, callback=on_msg)
    ws.agg_trade(symbol=symbol.lower(), id=3, callback=on_msg)
    try:
        while time.time()<stop_ts: await asyncio.sleep(0.1)
    finally:
        ws.stop(); os.makedirs(os.path.dirname(out_path), exist_ok=True)
        pd.DataFrame(rows).to_parquet(out_path); logger.info("record_done", extra={"extra": {"rows": len(rows), "out": out_path}})

def main()->None:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd")
    rec=sub.add_parser("record"); rec.add_argument("--symbol", required=True); rec.add_argument("--minutes", type=int, default=1); rec.add_argument("--out", required=True)
    args=ap.parse_args()
    if args.cmd=="record":
        from yaml import safe_load
        with open("config/config.yaml","r") as f: cfg=safe_load(f)
        asyncio.run(record(symbol=args.symbol, minutes=args.minutes, out_path=args.out,
                           mode=cfg["exchange"]["mode"], testnet=cfg["exchange"]["testnet"],
                           base_url_spot=cfg["exchange"]["base_url_spot"], base_url_futures=cfg["exchange"]["base_url_futures"],
                           ws_url_spot=cfg["exchange"]["ws_url_spot"], ws_url_futures=cfg["exchange"]["ws_url_futures"]))
if __name__=="__main__": main()
