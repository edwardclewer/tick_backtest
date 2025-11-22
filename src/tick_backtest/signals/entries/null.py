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

from typing import Dict

from tick_backtest.config_parsers.strategy.config_dataclass import EntryConfig
from tick_backtest.config_parsers.strategy.entry_configs import StubEntryParams
from tick_backtest.data_feed.tick import Tick
from tick_backtest.signals.entries.base import BaseEntryEngine, EntryResult


class NullEntryEngine(BaseEntryEngine):
    """No-op entry engine used for stubs/tests."""

    tp_multiple = 1.0
    sl_multiple = 1.0

    def __init__(self, entry_config: EntryConfig, pip_size: float) -> None:
        super().__init__(entry_config, pip_size)
        if not isinstance(entry_config.params, StubEntryParams):
            raise TypeError("NullEntryEngine expects StubEntryParams")

    def update(self, _tick: Tick, _metrics: Dict[str, float]) -> EntryResult:
        return EntryResult(reason=self.entry_config.name)
