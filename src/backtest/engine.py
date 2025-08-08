from __future__ import annotations
import argparse, os, math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src.data.orderbook import L2Book
from src.features.micro import ShortVolEWMA, make_feature_row, label_k_tick_ahead
from src.model.online import OnlineSGD
from src.strategy.maker import StrategyParams, decide_entry
from src.utils.log import get_logger
@dataclass
class Metrics:
    sharpe: float; sortino: float; hit_rate: float; avg_bps: float; max_dd: float; fill_rate: float; turnover: float

def queue_fill_sim(order_side: str, order_price: float, trade_price: float, trade_qty: float, my_queue: float)->Tuple[float,float]:
    if order_side=="BUY" and trade_price<=order_price:
        fill=min(trade_qty, my_queue); return fill, my_queue-fill
    if order_side=="SELL" and trade_price>=order_price:
        fill=min(trade_qty, my_queue); return fill, my_queue-fill
    return 0.0, my_queue

def compute_metrics(equity: List[float], pnl_trades: List[float], rets: List[float], fills: int, sent: int, turnover: float)->Metrics:
    arr=np.array(rets, dtype=float)
    sharpe=float(np.mean(arr)/(np.std(arr)+1e-9)*math.sqrt(252*24*60)) if len(arr)>1 else 0.0
    neg=arr[arr<0]; sortino=float(np.mean(arr)/(np.std(neg)+1e-9)*math.sqrt(252*24*60)) if len(neg)>1 else 0.0
    hit=float(np.mean([1.0 if x>0 else 0.0 for x in pnl_trades])) if pnl_trades else 0.0
    avg_bps=float(np.mean([x for x in pnl_trades])) if pnl_trades else 0.0
    mxdd=0.0; peak=-1e9
    for e in equity:
        peak=max(peak, e); mxdd=min(mxdd, e-peak)
    mxdd=-mxdd; fill_rate=fills/max(1, sent)
    return Metrics(sharpe, sortino, hit, avg_bps, mxdd, fill_rate, turnover)

def run_backtest(df: pd.DataFrame, symbol: str, maker_bps: float, taker_bps: float, latency_ms: int, slippage_bps: float, seed: int=123)->Metrics:
    logger=get_logger("backtest"); np.random.seed(seed)
    book=L2Book(); vol=ShortVolEWMA(alpha=0.06); model=OnlineSGD(); params=StrategyParams()
    equity=[0.0]; pnl_trades: List[float]=[]; rets: List[float]=[]; pos=0.0; turnover=0.0
    feats_window: List[dict]=[]; labels: List[int]=[]; mids_hist: List[float]=[]
    prev_bids=[]; prev_asks=[]; live_order: Dict[str,Any]={}; sent=0; fills=0
    for _, row in df.iterrows():
        t=row.get("ts_recv",0); etype=row.get("e") or row.get("eventType") or ""
        if "u" in row or etype in ("24hrTicker","bookTicker"):
            bb=float(row.get("b", row.get("bestBid", 0.0)) or 0.0)
            bq=float(row.get("B", row.get("bestBidQty", 0.0)) or 0.0)
            ba=float(row.get("a", row.get("bestAsk", 0.0)) or 0.0)
            aq=float(row.get("A", row.get("bestAskQty", 0.0)) or 0.0)
            bids=[(bb,bq)]; asks=[(ba,aq)]; book.update_snapshot(bids, asks)
            feat=make_feature_row(bb,bq,ba,aq,bids,asks,prev_bids,prev_asks,vol,n=5); prev_bids, prev_asks=bids, asks
            mids_hist.append(feat["mid"])
            k=5
            if len(mids_hist)>k:
                y=label_k_tick_ahead(mids_hist[-(k+1):], k=k, thresh_bps=2.0)
                feats_window.append(feat); labels.append(y)
                if len(feats_window)>=50: model.partial_fit(feats_window[-50:], labels[-50:])
            if model.inited:
                p_up=model.predict_proba_up(feat); decision=decide_entry(p_up, feat["spread_bps"], feat["imb"], proba_threshold=0.6)
                if decision.side and not live_order:
                    mid=feat["mid"]; tick=max(1e-2, (book.spread() or 1e-2)/2.0); notional=50.0
                    price=mid - tick if decision.side=='BUY' else mid + tick
                    qty=max(1e-6, notional/max(price,1e-9))
                    live_order={"side":decision.side, "price":price, "qty":qty, "queue":qty, "ts":t}; sent+=1
        if "p" in row and "q" in row and live_order:
            trade_price=float(row["p"]); trade_qty=float(row["q"])
            fill_qty, new_q=queue_fill_sim(live_order["side"], live_order["price"], trade_price, trade_qty, live_order["queue"])
            live_order["queue"]=new_q
            if fill_qty>0:
                fills+=1; fee_bps=maker_bps
                mid=(book.mid() or trade_price)
                pnl_bps=(mid - live_order["price"])/mid*1e4 if live_order["side"]=="BUY" else (live_order["price"] - mid)/mid*1e4
                pnl_bps-=fee_bps; pnl_trades.append(pnl_bps)
                pos+=fill_qty if live_order["side"]=="BUY" else -fill_qty; turnover+=abs(fill_qty)
                equity.append(equity[-1]+pnl_bps); rets.append(pnl_bps/1e4); live_order={}
    m=compute_metrics(equity, pnl_trades, rets, fills, sent, turnover)
    out_dir = os.path.join(os.path.dirname(__file__), "../../data/backtest")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    import matplotlib.pyplot as plt
    plt.figure(); plt.plot(equity); plt.title(f"Equity Curve ({symbol})"); plt.xlabel("trade"); plt.ylabel("bps"); plt.tight_layout()
    plt.savefig(os.path.join(root, out_dir, f"{symbol}_equity.png"))
    return m

def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument("--input", required=True); ap.add_argument("--symbol", default="BTCUSDT")
    args=ap.parse_args(); df = pd.read_csv(args.input) if args.input.endswith('.csv') else pd.read_parquet(args.input)
    m=run_backtest(df, symbol=args.symbol, maker_bps=9.0, taker_bps=10.0, latency_ms=80, slippage_bps=0.1)
    print("Sharpe:", m.sharpe, "Sortino:", m.sortino, "Win:", m.hit_rate, "Avg bps:", m.avg_bps, "MaxDD:", m.max_dd, "Fill:", m.fill_rate, "Turnover:", m.turnover)
if __name__=="__main__": main()
