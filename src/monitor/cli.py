from __future__ import annotations
import argparse, time, json
from rich.console import Console
from rich.table import Table

def render(log_path: str)->None:
    c=Console(); last_pos=0; pnl=0.0; ords=0; dd=0.0; ratelimit_blocks=0
    while True:
        try:
            with open(log_path, "r") as f:
                f.seek(last_pos)
                for line in f:
                    evt=json.loads(line)
                    if evt.get("name")=="risk" and "kill_switch_trigger" in evt.get("msg",""): dd = evt.get("extra", {}).get("dd_pct", dd)
                    if evt.get("name")=="risk" and "pnl_update" in evt.get("msg",""): pnl = evt.get("extra", {}).get("pnl_day", pnl)
                    if "order_placed" in evt.get("msg",""): ords += 1
                    if "ratelimit_block" in evt.get("msg",""): ratelimit_blocks += 1
                last_pos=f.tell()
        except FileNotFoundError: pass
        tbl=Table(title="Scalper Monitor"); tbl.add_column("PnL (day)"); tbl.add_column("Orders"); tbl.add_column("DD%"); tbl.add_column("RateLimit Blocks")
        tbl.add_row(f"{pnl:.2f}", str(ords), f"{dd:.2f}", str(ratelimit_blocks)); c.clear(); c.print(tbl); time.sleep(1)

def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument("--log", default="data/logs/trade.jsonl"); args=ap.parse_args(); render(args.log)
if __name__=="__main__": main()
