"""Entry point for the Hyperliquid LLM trading bot."""
from __future__ import annotations

import logging
import time

from .config import load_settings
from .datafeed import MarketDataFeed
from .execution import decision_to_order, submit_order
from .hl_client import HyperliquidClient
from .risk import DailyRiskManager, calculate_open_risk
from .storage import init_db
from .strategy.controller import StrategyController

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def run_loop() -> None:
    settings = load_settings()
    configure_logging()
    LOGGER.info("Launching Hyperliquid LLM bot on %s", settings.hl_network)
    init_db(settings)

    client = HyperliquidClient(settings)
    feed = MarketDataFeed(client, settings)
    controller = StrategyController(settings)
    risk_manager = DailyRiskManager(settings)

    try:
        while True:
            risk_manager.reset_if_needed()
            positions = client.get_positions()
            open_positions = {symbol: pos for symbol, pos in positions.items() if not pos.is_flat()}
            active_symbols = set(open_positions.keys())
            for symbol in list(risk_manager.open_r_by_symbol.keys()):
                if symbol not in active_symbols:
                    risk_manager.release_open_risk(symbol)

            for symbol in settings.symbols:
                position = positions[symbol]
                state = feed.build_market_state(symbol, position)
                risk_manager.register_market_state(state)
                if risk_manager.kill_switch_triggered:
                    LOGGER.warning("Daily kill switch active; skipping new trades")
                    break
                if risk_manager.in_cool_off(symbol):
                    LOGGER.info("Symbol %s cooling off; skipping", symbol)
                    continue

                decision = controller.decide(state)
                order = decision_to_order(decision, state, settings)
                if order is None:
                    continue

                is_new_position = position.is_flat()
                if is_new_position and not risk_manager.can_open_new_position(len(open_positions)):
                    LOGGER.info("Max concurrent positions reached; skipping %s", symbol)
                    continue

                open_risk = calculate_open_risk(
                    size=order.size,
                    entry_price=state.price,
                    stop_price=order.stop_price or state.price,
                    equity=state.equity,
                    base_risk_pct=settings.base_risk_pct,
                )
                if not risk_manager.can_add_risk(symbol, open_risk):
                    LOGGER.info("Open risk cap reached; skipping %s", symbol)
                    continue

                try:
                    submit_order(order, decision, state, settings, client)
                except NotImplementedError:
                    LOGGER.error("Live execution not implemented; enable DRY_RUN=1")
                    return

                risk_manager.add_open_risk(symbol, open_risk)
                if is_new_position:
                    open_positions[symbol] = position

            time.sleep(5)
    except KeyboardInterrupt:
        LOGGER.info("Shutting down trading loop")


def main() -> None:
    run_loop()


if __name__ == "__main__":
    main()
