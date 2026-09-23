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

"""Tests for helpers in `data_feed.data_feed`."""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest

from tick_backtest.data_feed.data_feed import get_data_months
from tick_backtest.data_feed.validation import TickValidator
from tick_backtest.exceptions import DataFeedError


def test_data_feed_selector_defaults_to_streaming_python_loader(monkeypatch):
    """Default DataFeed should stream parquet batches instead of reading whole shards."""

    monkeypatch.delenv("TICK_BACKTEST_USE_COMPILED_DATA_FEED", raising=False)

    import tick_backtest.data_feed.data_feed as data_feed_selector

    data_feed_selector = importlib.reload(data_feed_selector)

    assert data_feed_selector.DataFeed.__module__ == "tick_backtest.data_feed._data_feed_py"


def test_tick_selector_defaults_to_python_nanosecond_tick(monkeypatch):
    """Streaming DataFeed needs a Tick class that accepts timestamp_ns."""

    monkeypatch.delenv("TICK_BACKTEST_USE_COMPILED_DATA_FEED", raising=False)

    import tick_backtest.data_feed.tick as tick_module

    tick_module = importlib.reload(tick_module)
    tick = tick_module.Tick(
        1.0,
        100.0,
        100.1,
        100.05,
        timestamp_ns=1_000_000_123,
    )

    assert tick.timestamp_ns == 1_000_000_123
    assert tick.timestamp == pytest.approx(1.000000123)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_data_feed_selector_compiled_opt_in_values(monkeypatch, value):
    """Compiled DataFeed should require an explicit opt-in flag."""

    monkeypatch.setenv("TICK_BACKTEST_USE_COMPILED_DATA_FEED", value)

    import tick_backtest.data_feed.data_feed as data_feed_selector

    data_feed_selector = importlib.reload(data_feed_selector)

    assert data_feed_selector._use_compiled_data_feed()
    if importlib.util.find_spec("tick_backtest.data_feed._data_feed") is not None:
        assert data_feed_selector.DataFeed.__module__ == "tick_backtest.data_feed._data_feed"

    monkeypatch.delenv("TICK_BACKTEST_USE_COMPILED_DATA_FEED", raising=False)
    importlib.reload(data_feed_selector)


def test_compiled_data_feed_streams_record_batches(monkeypatch, tmp_path):
    """Compiled DataFeed should not materialize a full parquet shard."""

    compiled_feed = pytest.importorskip("tick_backtest.data_feed._data_feed")

    pair = "EURUSD"
    base_path = tmp_path / "ticks"
    shard = base_path / pair / f"{pair}_2024-01.parquet"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_bytes(b"stub")

    timestamp_ns = [
        1_700_000_000_000_000_001,
        1_700_000_000_000_000_002,
    ]

    class FakeColumn:
        def __init__(self, values):
            self.values = values

        def to_numpy(self, *, zero_copy_only=False):
            return np.asarray(self.values)

        def to_pandas(self):
            return pd.Series(pd.to_datetime(self.values, utc=True))

    class FakeBatch:
        def __init__(self, bids, asks, timestamps):
            self._columns = {
                "bid": FakeColumn(bids),
                "ask": FakeColumn(asks),
                "timestamp": FakeColumn(timestamps),
            }

        def column(self, name):
            return self._columns[name]

    class FakeParquetFile:
        def __init__(self, path):
            assert path == shard

        def iter_batches(self, *, batch_size, columns):
            assert batch_size == 1
            assert columns == ["timestamp", "bid", "ask"]
            return iter(
                [
                    FakeBatch([1.0], [1.2], [timestamp_ns[0]]),
                    FakeBatch([1.1], [1.3], [timestamp_ns[1]]),
                ]
            )

    def fail_full_file_read(*_args, **_kwargs):
        raise AssertionError("compiled DataFeed must use iter_batches, not read_table")

    monkeypatch.setattr(compiled_feed.pq, "ParquetFile", FakeParquetFile)
    monkeypatch.setattr(compiled_feed.pq, "read_table", fail_full_file_read)

    feed = compiled_feed.DataFeed(
        base_path=str(base_path),
        pair=pair,
        year_start=2024,
        year_end=2024,
        month_start=1,
        month_end=1,
        batch_size=1,
    )

    first = feed.tick()
    second = feed.tick()

    assert first.bid == 1.0
    assert first.ask == 1.2
    assert first.timestamp_ns == timestamp_ns[0]
    assert second.bid == 1.1
    assert second.ask == 1.3
    assert second.timestamp_ns == timestamp_ns[1]


def test_get_data_months_handles_single_year():
    """Expect inclusive month range when start and end share a year."""

    months = get_data_months(2015, 2015, 1, 3)
    assert months == [[2015, 1], [2015, 2], [2015, 3]]


def test_get_data_months_cross_year_range():
    """Ensure spans across years cover all interior months."""

    months = get_data_months(2014, 2015, 11, 2)
    assert months[:2] == [[2014, 11], [2014, 12]]
    assert months[-2:] == [[2015, 1], [2015, 2]]
    assert len(months) == 4


def test_get_data_months_invalid_month_range():
    """Month start must be <= month end when the year is fixed."""

    with pytest.raises(DataFeedError):
        get_data_months(2015, 2015, 6, 3)


def test_get_data_months_rejects_start_after_end():
    """Cross-year ordering must still respect chronological ordering."""

    with pytest.raises(DataFeedError):
        get_data_months(2020, 2019, 12, 1)


def test_get_data_months_accepts_future_years():
    """No hard-coded upper bound should block future datasets."""

    months = get_data_months(2030, 2030, 5, 5)
    assert months == [[2030, 5]]


def test_tick_validator_uses_nanosecond_timestamps():
    """Validator should treat nanosecond regression as an error."""

    class DummyTick:
        def __init__(self, ts_ns):
            self.timestamp_ns = ts_ns
            self.bid = 1.1000
            self.ask = 1.1002
            self.mid = 1.1001

    validator = TickValidator(pair="EURUSD")
    assert validator.validate(DummyTick(1_000_000_000_000_000_000))
    assert validator.validate(DummyTick(1_000_000_000_000_000_010))
    assert not validator.validate(DummyTick(1_000_000_000_000_000_005))
    assert validator.stats.issues["timestamp_regression"] == 1


def test_python_data_feed_raises_on_corrupt_parquet(monkeypatch, tmp_path):
    """Fallback DataFeed should surface DataFeedError when parquet shards are corrupt."""

    import tick_backtest.data_feed._data_feed_py as data_feed_py

    pair = "EURUSD"
    base_path = tmp_path / "ticks"
    shard = base_path / pair / f"{pair}_2024-01.parquet"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_bytes(b"")

    class FailingParquet:
        def __init__(self, *_args, **_kwargs):
            pass

        def iter_batches(self, batch_size):
            def _iterator():
                raise ValueError("corrupt shard")
                yield  # pragma: no cover

            return _iterator()

    monkeypatch.setattr(data_feed_py.pq, "ParquetFile", FailingParquet)

    feed = data_feed_py.DataFeed(
        base_path=str(base_path),
        pair=pair,
        year_start=2024,
        year_end=2024,
        month_start=1,
        month_end=1,
        batch_size=1,
    )

    with pytest.raises(data_feed_py.DataFeedError):
        feed.tick()
