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

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from tick_backtest.metrics.primitives._ewma_py import PyEWMA
from tick_backtest.metrics.primitives._time_rolling_window_py import PyTimeRollingWindow
from tick_backtest.metrics.primitives._time_weighted_histogram_py import PyTimeWeightedHistogram


@dataclass
class RollingWindowReference:
    """Incremental helper mirroring TimeRollingWindow behaviour."""

    lookback_seconds: float
    window: PyTimeRollingWindow = None  # type: ignore[assignment]
    last_timestamp: Optional[float] = None

    def __post_init__(self) -> None:
        self.window = PyTimeRollingWindow(lookback_seconds=self.lookback_seconds)

    def update(self, timestamp: float, value: float) -> Tuple[float, float]:
        if self.last_timestamp is None:
            dt = 0.0
        else:
            dt = timestamp - self.last_timestamp
            if dt < 1e-6:
                dt = 1e-6
        self.window.append(ts=timestamp, value=value, dt=dt)
        self.last_timestamp = timestamp
        return self.window.stats()


def ewma_sequence(
    timestamps: Sequence[float],
    values: Sequence[float],
    tau_seconds: float,
    *,
    power: int = 1,
) -> List[float]:
    """Generate EWMA values matching the primitive implementation."""

    smoother = PyEWMA(tau_seconds=tau_seconds, power=power)
    output: List[float] = []
    last_val = 0.0
    for idx, (ts, value) in enumerate(zip(timestamps, values)):
        last_val = smoother.update(ts, value)
        if idx == 0:
            # Primitive returns zero until warmed up; align with metric expectations.
            output.append(0.0)
        else:
            output.append(last_val)
    return output


def ewma_metric_expected(
    timestamps: Sequence[float],
    prices: Sequence[float],
    tau_seconds: float,
) -> List[float]:
    """Replicate EWMAMetric behaviour (initial seed = first price)."""

    results: List[float] = []
    last_value = math.nan
    last_ts = math.nan
    for ts, price in zip(timestamps, prices):
        if math.isnan(last_value):
            last_value = price
            last_ts = ts
            results.append(last_value)
            continue

        dt = max(1e-6, ts - last_ts)
        alpha = 1.0 - math.exp(-dt / tau_seconds)
        last_value = (1.0 - alpha) * last_value + alpha * price
        last_ts = ts
        results.append(last_value)
    return results


def ewma_slope_expected(
    timestamps: Sequence[float],
    prices: Sequence[float],
    tau_seconds: float,
    window_seconds: float,
) -> List[Tuple[float, float]]:
    """Return (ewma, slope) pairs mirroring EWMASlopeMetric fallback."""

    history: List[Tuple[float, float]] = []
    ewma_values = ewma_metric_expected(timestamps, prices, tau_seconds)
    slopes: List[Tuple[float, float]] = []

    for ts, ewma in zip(timestamps, ewma_values):
        history.append((ts, ewma))
        cutoff = ts - window_seconds
        while len(history) > 1 and history[0][0] < cutoff:
            history.pop(0)

        if len(history) < 2:
            slopes.append((ewma, math.nan))
            continue

        oldest_t, oldest_v = history[0]
        dt = max(1e-6, ts - oldest_t)
        slope = (ewma - oldest_v) / dt
        slopes.append((ewma, slope))
    return slopes


def drift_expected(
    timestamps: Sequence[float],
    mids: Sequence[float],
    lookback_seconds: float,
) -> List[Tuple[float, int]]:
    """Replicate DriftSignMetric behaviour using the Python rolling window."""

    window = PyTimeRollingWindow(lookback_seconds=lookback_seconds)
    results: List[Tuple[float, int]] = []
    last_ts = None

    for ts, mid in zip(timestamps, mids):
        if last_ts is None:
            dt = 0.0
        else:
            dt = ts - last_ts
            if dt < 1e-6:
                dt = 1e-6
        window.append(ts=ts, value=mid, dt=dt)
        last_ts = ts

        mean, _ = window.stats()
        if not math.isfinite(mean):
            results.append((math.nan, 0))
            continue

        drift = (mid - mean) / lookback_seconds
        sign = 1 if drift > 0.0 else -1 if drift < 0.0 else 0
        results.append((drift, sign))

    return results


def ewma_vol_expected(
    timestamps: Sequence[float],
    mids: Sequence[float],
    *,
    tau_seconds: float,
    percentile_horizon_seconds: float,
    bins: int,
    base_vol: float,
    stddev_cap: float,
) -> List[Tuple[float, float]]:
    """Replicate EWMAVolMetric outputs using Python primitives."""

    edges = np.linspace(
        0.0,
        (stddev_cap * base_vol) ** 2,
        bins + 1,
        dtype=np.float64,
    )
    hist = PyTimeWeightedHistogram(edges, percentile_horizon_seconds)
    smoother = PyEWMA(tau_seconds=tau_seconds, power=2)

    outputs: List[Tuple[float, float]] = []
    last_t = None
    last_mid = None

    for ts, mid in zip(timestamps, mids):
        if last_t is None or last_mid is None:
            last_t = ts
            last_mid = mid
            outputs.append((0.0, math.nan))
            continue

        dt = ts - last_t
        if dt < 1e-6:
            dt = 1e-6

        if mid > 0.0 and last_mid > 0.0:
            ret = math.log(mid / last_mid)
        else:
            ret = 0.0

        ewma_val = smoother.update(ts, ret)
        hist.add(ts - dt, ts, ewma_val)
        hist.trim(ts)
        pct = hist.percentile_rank(ewma_val)

        last_t = ts
        last_mid = mid
        outputs.append((ewma_val, pct))

    return outputs


def spread_percentile_reference(history: Sequence[Tuple[float, float]], current: float) -> float:
    """Return empirical percentile identical to SpreadMetric (<= comparator)."""

    if not history:
        return math.nan
    count = sum(1 for _, value in history if value <= current)
    return count / len(history)


def tick_rate_expected(timestamps: Sequence[float], window_seconds: float) -> List[Tuple[int, float, float]]:
    """Return counts and rates matching TickRateMetric fallback."""

    history: List[float] = []
    outputs: List[Tuple[int, float, float]] = []
    for ts in timestamps:
        history.append(ts)
        cutoff = ts - window_seconds
        history = [point for point in history if point > cutoff]
        count = len(history)
        rate_sec = count / window_seconds
        outputs.append((count, rate_sec, rate_sec * 60.0))
    return outputs
