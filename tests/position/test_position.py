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

"""Tests for the `Position` entity."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tick_backtest.position.position import Position


def test_position_close_computes_pnl_pips():
    """Closing a trade should compute PnL in pips respecting direction."""

    entry_time = datetime(2015, 1, 1, tzinfo=timezone.utc)
    exit_time = datetime(2015, 1, 1, 0, 10, tzinfo=timezone.utc)
    position = Position(entry_time=entry_time, entry_price=1.1000, direction=1, tp=1.1010, sl=1.0990)

    position.close(exit_price=1.1010, exit_time=exit_time, pip_size=0.0001, exit_reason="")

    assert position.pnl_pips == pytest.approx(10.0)
    assert position.exit_time == exit_time
    assert position.exit_price == 1.1010


def test_position_outcome_label_tp_vs_sl():
    """Outcome label should reflect whether TP or SL triggered."""

    pos_long = Position(entry_price=1.1000, tp=1.1010, sl=1.0990, direction=1)
    pos_long.close(exit_price=1.1010, exit_time=datetime.now(timezone.utc), pip_size=0.0001, exit_reason="")
    assert pos_long.outcome_label == "TP"

    pos_short = Position(entry_price=1.1000, tp=1.0990, sl=1.1010, direction=-1)
    pos_short.close(exit_price=1.1010, exit_time=datetime.now(timezone.utc), pip_size=0.0001, exit_reason="")
    assert pos_short.outcome_label == "SL"


def test_position_is_open_property():
    """`is_open` toggles once the position has been closed."""

    pos = Position()
    assert pos.is_open

    pos.close(exit_price=1.0, exit_time=datetime.now(timezone.utc), pip_size=0.0001, exit_reason="")
    assert not pos.is_open


def test_position_close_respects_exit_reason_override():
    """Explicit exit reason should override automatic TP/SL classification."""

    position = Position(entry_price=1.1000, tp=1.2000, sl=1.0500, direction=1)
    position.close(
        exit_price=1.1500,
        exit_time=datetime.now(timezone.utc),
        pip_size=0.0001,
        exit_reason="manual_exit",
    )

    assert position.outcome_label == "manual_exit"
