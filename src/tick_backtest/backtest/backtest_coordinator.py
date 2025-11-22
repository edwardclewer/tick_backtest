# Copyright 2025 Edward Clewer
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import logging
from tick_backtest.backtest.backtest import Backtest
from tick_backtest.data_feed.data_feed import DataFeed, DataFeedError, NoMoreTicks
from tick_backtest.data_feed.validation import TickValidator, ValidatingDataFeed
from tick_backtest.logging_utils import run_context
from tick_backtest.metrics.manager.metrics_manager import MetricsManager
from tick_backtest.signals.signal_generator import SignalGenerator


logger = logging.getLogger(__name__)

class BacktestCoordinator:
    def __init__(
        self,
        backtest_config,
        *,
        run_id: str,
        ):
        self.backtest_config = backtest_config
        self.backtest_config.output_base_path.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.pair_failures: dict[str, str] = {}
        self.tick_validation_stats: dict[str, TickValidator] = {}

    def run_backtests(self):
        """Run a backtest for each configured pair."""
        logger.info(
            "starting backtest run",
            extra={"pairs": list(self.backtest_config.pairs)},
        )
        for pair in self.backtest_config.pairs:
            with run_context(pair=pair):
                logger.info("starting pair backtest")
                try:
                    self._run_backtest(pair)
                except (DataFeedError, FileNotFoundError) as exc:
                    self.pair_failures[pair] = str(exc)
                    logger.error("failed to prepare data feed; skipping pair", extra={"error": str(exc)})
                    continue
                logger.info("completed pair backtest")
        logger.info("all backtests complete")

    def _run_backtest(self, pair: str):
        """Run a single backtest for the supplied pair."""
        raw_feed = DataFeed(
            base_path=self.backtest_config.data_base_path,
            pair=pair,
            year_start=self.backtest_config.year_start,
            year_end=self.backtest_config.year_end,
            month_start=self.backtest_config.month_start,
            month_end=self.backtest_config.month_end
        )

        validator = TickValidator(pair=pair)
        data_feed = ValidatingDataFeed(raw_feed, validator)

        metrics_manager = MetricsManager(self.backtest_config.metrics_config_path)
        signal_generator = SignalGenerator(
            strategy_config=self.backtest_config.strategy_config,
            pip_size=self.backtest_config.pip_size,
        )

        pair_output_dir = self.backtest_config.output_base_path / pair
        pair_output_dir.mkdir(parents=True, exist_ok=True)
        trades_path = pair_output_dir / "trades.parquet"

        try:
            initial_tick = data_feed.tick()
        except NoMoreTicks:
            logger.warning("no data available for pair; skipping")
            self.tick_validation_stats[pair] = validator
            return

        backtest = Backtest(
            data_feed=data_feed,
            signal_generator=signal_generator,
            metrics_manager=metrics_manager,
            output_base_path=trades_path,
            pip_size=self.backtest_config.pip_size
        )
        try:
            backtest.warmup(initial_tick=initial_tick, warmup_seconds=self.backtest_config.warmup_seconds)
            backtest.run()
        except Exception as exc:  # pragma: no cover - exercised via unit tests
            self.pair_failures[pair] = str(exc)
            logger.exception("pair backtest failed", extra={"pair": pair})
            self.tick_validation_stats[pair] = validator
            return
        self.tick_validation_stats[pair] = validator
