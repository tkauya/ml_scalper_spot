"""Performance evaluation utilities."""
from __future__ import annotations

import math
from typing import Dict

import pandas as pd

from .storage import closed_trades_dataframe, record_metric


def _max_drawdown(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    cumulative = series.cumsum()
    rolling_max = cumulative.cummax()
    drawdown = cumulative - rolling_max
    return drawdown.min()


def summarize_performance() -> Dict[str, float]:
    """Compute a light-weight performance summary for closed trades."""

    df = closed_trades_dataframe()
    if df.empty:
        return {"total_pnl": 0.0, "daily_sharpe": 0.0, "max_drawdown": 0.0}

    df = df.copy()
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    daily_pnl = df.groupby("date")["pnl"].sum()

    total_pnl = float(daily_pnl.sum())
    sharpe = 0.0
    if len(daily_pnl) > 1 and daily_pnl.std() > 1e-9:
        sharpe = float((daily_pnl.mean() / daily_pnl.std()) * math.sqrt(252))

    max_dd = float(_max_drawdown(daily_pnl))

    record_metric("total_pnl", total_pnl)
    record_metric("daily_sharpe", sharpe)
    record_metric("max_drawdown", max_dd)

    return {"total_pnl": total_pnl, "daily_sharpe": sharpe, "max_drawdown": max_dd}


__all__ = ["summarize_performance"]
