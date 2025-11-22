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

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Position:
    """
    Represents an open or closed trade position.
    """
    entry_time: Optional[datetime] = None
    entry_price: float = 0.0
    tp: Optional[float] = None
    sl: Optional[float] = None
    direction: int = 0             # +1 long, -1 short
    timeout_seconds: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl_pips: Optional[float] = None
    outcome_label: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    # --- Lifecycle helpers ---

    def set_entry_fill(self, price: float, fill_time: datetime) -> None:
        """Record the fill price/time once the trade actually opens."""
        self.entry_price = price
        self.entry_time = fill_time

    def close(self, exit_price: float, exit_time: datetime, pip_size: float, exit_reason: str) -> None:
        """Close position and compute realized PnL."""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.pnl_pips = (exit_price - self.entry_price) * self.direction / pip_size
        if exit_reason:
            self.outcome_label = exit_reason
            return

        label = "EXIT"
        if self.direction == 1:
            if self.tp is not None and exit_price >= self.tp:
                label = "TP"
            elif self.sl is not None and exit_price <= self.sl:
                label = "SL"
        elif self.direction == -1:
            if self.tp is not None and exit_price <= self.tp:
                label = "TP"
            elif self.sl is not None and exit_price >= self.sl:
                label = "SL"

        self.outcome_label = label

    @property
    def is_open(self) -> bool:
        """Return True if position not yet closed."""
        return self.exit_time is None
