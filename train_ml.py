"""Train the win-rate gate classifier."""
from __future__ import annotations

import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

from src.config import load_settings
from src.storage import closed_trades_dataframe, init_db

LOGGER = logging.getLogger(__name__)


def train_gate(model_path: Path) -> None:
    settings = load_settings()
    init_db(settings)
    df = closed_trades_dataframe()
    if df.empty:
        print("No closed trades yet; nothing to train.")
        return
    df = df.dropna(subset=["stop_price", "pnl", "size"])
    df["risk_per_unit"] = (df["entry_price"] - df["stop_price"]).abs()
    df["risk_amount"] = df["risk_per_unit"] * df["size"].abs()
    df = df[df["risk_amount"] > 0]
    if df.empty:
        print("Not enough risk data to train gate.")
        return
    df["target"] = (df["pnl"] >= df["risk_amount"]).astype(int)
    if df["target"].nunique() < 2:
        print("Need both wins and losses to train gate.")
        return

    features = pd.DataFrame(
        {
            "abs_size": df["size"].abs(),
            "risk_per_unit": df["risk_per_unit"],
            "confidence": df["confidence"],
            "symbol_id": df["symbol"].astype("category").cat.codes,
        }
    )
    model = GradientBoostingClassifier(random_state=42)
    model.fit(features, df["target"])
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    print(f"Saved ML gate to {model_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    train_gate(Path(settings.ml_gate_path))
