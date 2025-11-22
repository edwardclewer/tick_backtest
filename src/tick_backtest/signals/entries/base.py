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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

from tick_backtest.config_parsers.strategy.config_dataclass import EntryConfig
from tick_backtest.data_feed.tick import Tick


@dataclass
class EntryResult:
    """Structured response produced by entry engines."""

    should_open: bool = False
    direction: int = 0
    tp: Optional[float] = None
    sl: Optional[float] = None
    timeout_seconds: Optional[float] = None
    reason: str = "no_signal"
    metadata: Optional[Dict[str, float]] = None


class BaseEntryEngine(ABC):
    """Interface for entry engines. Implementations must be stateless or encode their own state."""

    def __init__(self, entry_config: EntryConfig, pip_size: float) -> None:
        self.entry_config = entry_config
        self.pip_size = float(pip_size)

    @abstractmethod
    def update(self, tick: Tick, metrics: Dict[str, float]) -> EntryResult:
        """Return the latest entry decision given current metrics."""

