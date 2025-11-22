<!--
Copyright 2025 Edward Clewer

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Metrics Reference

This page documents every metric type available through the `config/metrics/*.yaml` files. All metrics share the same wrapper fields:

- `name` — unique identifier. At runtime each output is prefixed as `<name>.<field>`.
- `type` — registry key in `tick_backtest.config_parsers.metrics.config_registry.CONFIG_REGISTRY`.
- `enabled` — optional boolean (defaults to `true`). Disabled metrics are skipped during the run.
- `params` — engine-specific arguments described below.

Once loaded, the `MetricsManager` returns a flat dictionary of key/value pairs. Consumers (signals, predicates, analysis) reference values via `<metric_name>.<output_field>`.

## Summary

| Type | Typical Outputs | Purpose |
| --- | --- | --- |
| `zscore` | `rolling_residual`, `z_score` | Time-weighted z-score of the mid price over a rolling window. |
| `ewma` | `ewma` | Exponentially weighted moving average of bid/ask/mid. |
| `ewma_slope` | `ewma`, `slope` | EWMA with an additional slope estimate across a recent horizon. |
| `ewma_vol` | `vol_ewma`, `vol_percentile` | EWMA of log-return variance with percentile stratification. |
| `drift_sign` | `drift`, `drift_sign` | Directional drift of the mid price over a rolling window. |
| `session` | `session_label` | UTC session label (`Asia`, `London`, `London_New_York_Overlap`, `New_York`, `Other`). |
| `spread` | `spread`, `spread_pips`, `spread_percentile` | Spread magnitude and percentile over a trailing horizon. |
| `tick_rate` | `tick_count`, `tick_rate_per_sec`, `tick_rate_per_min` | Tick throughput within a sliding window. |

---

## Signal Strength Metrics

Momentum and mean-reversion indicators quantify how unusual the current price is relative to a trailing baseline.

### `zscore` — Rolling Z-Score

**YAML type:** `zscore`

Computes a time-weighted mean and standard deviation of the mid price, then exposes the residual and z-score for the most recent tick. Invalid or insufficient data yields zeros.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `lookback_seconds` | int | ✅ | Horizon for the time-weighted statistics. Must be a positive integer. |

**Outputs**

| Field | Description |
| --- | --- |
| `rolling_residual` | Difference between the latest mid price and the rolling mean. |
| `z_score` | Residual divided by the rolling standard deviation (0 when variance ≤ 0). |

**Notes**
- Metrics warm up; the first few ticks may report `0.0` until variance becomes positive.
- Use predicates against `<name>.z_score` or `<name>.rolling_residual` for threshold logic.

Example:

```yaml
- name: z30m
  type: zscore
  params:
    lookback_seconds: 1800
```

---

### `ewma` — Exponentially Weighted Moving Average

**YAML type:** `ewma`

Tracks an exponentially weighted moving average of the chosen price field (`mid` by default). The first tick seeds the EWMA with the observed price unless `initial_value` is supplied.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `tau_seconds` | float | ✅ | – | Decay constant τ (larger values smooth more). Must be positive. |
| `initial_value` | float | ❌ | `null` | Optional explicit starting value. |
| `price_field` | string | ❌ | `"mid"` | Which tick field to sample (`mid`, `bid`, or `ask`). |

**Outputs**

| Field | Description |
| --- | --- |
| `ewma` | Latest exponentially weighted average. |

Example:

```yaml
- name: ewma_mid_5m
  type: ewma
  params:
    tau_seconds: 300
    price_field: mid
```

---

### `ewma_slope` — EWMA with Slope Estimate

**YAML type:** `ewma_slope`

Extends the EWMA by adding a finite-difference slope computed over a trailing window (`window_seconds`). Useful for detecting trend strength while keeping a smoothed price estimate.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `tau_seconds` | float | ✅ | – | EWMA decay constant. |
| `window_seconds` | float | ✅ | – | Horizon used to compute the slope. Must be positive. |
| `initial_value` | float | ❌ | `null` | Optional initial EWMA value. |
| `price_field` | string | ❌ | `"mid"` | Tick field to sample (`mid`, `bid`, `ask`). |

**Outputs**

| Field | Description |
| --- | --- |
| `ewma` | The current EWMA value. |
| `slope` | `(ewma_now - ewma_then) / dt` using the oldest retained observation inside `window_seconds`. |

**Notes**
- The slope is `NaN` until at least two observations fall within the window.
- No external metric dependency: the engine maintains its own EWMA history.

---

## Volatility Metrics

These metrics characterise the prevailing volatility regime and where the current variance sits relative to history.

### `ewma_vol` — EWMA of Variance with Percentile Stratification

**YAML type:** `ewma_vol`

Computes an EWMA of squared log returns (variance proxy) and records the current level relative to a time-weighted histogram. Useful for volatility regime filtering and stratification.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `tau_seconds` | float | ✅ | – | EWMA decay constant for variance. |
| `percentile_horizon_seconds` | float | ✅ | – | Horizon used by the histogram when computing percentiles. |
| `bins` | int | ✅ | – | Number of histogram bins (`2`–`10 000`). |
| `base_vol` | float | ✅ | – | Baseline standard deviation used to scale the histogram range. |
| `stddev_cap` | float | ❌ | `5.0` | Upper bound multiple; range = `(stddev_cap × base_vol)^2`. |

**Outputs**

| Field | Description |
| --- | --- |
| `vol_ewma` | Latest EWMA of squared log returns. |
| `vol_percentile` | Percentile rank (0–1) of `vol_ewma` within the histogram. |

**Notes**
- `vol_percentile` returns `NaN` until enough history accumulates to populate the histogram.
- Choose `base_vol` and `stddev_cap` to cover expected variance regimes; over-wide ranges reduce percentile resolution.

Example:

```yaml
- name: ewma_vol_5m
  type: ewma_vol
  params:
    tau_seconds: 300
    percentile_horizon_seconds: 300
    bins: 256
    base_vol: 0.0001
    stddev_cap: 5.0
```

---

## Trend & Direction Metrics

Indicators that capture directional drift or session context to augment entry predicates.

### `drift_sign` — Directional Drift

**YAML type:** `drift_sign`

Measures the directional drift of the mid price over a rolling window. The sign indicates whether price is above (`+1`), below (`-1`), or near (`0`) the rolling mean.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `lookback_seconds` | int | ✅ | Rolling window for the time-weighted mean. Must be positive. |

**Outputs**

| Field | Description |
| --- | --- |
| `drift` | Difference between the mid price and rolling mean scaled by the window (units: price per second). |
| `drift_sign` | Integer in `{-1, 0, 1}` indicating drift direction. |

**Notes**
- The first few ticks may report neutral values until the window has data.
- Combine with predicates to require alignment with longer-term trend.

---

### `session` — UTC Trading Session

**YAML type:** `session`

Tags each tick with the trading session inferred from UTC time-of-day.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| *(none)* | – | – | Only the standard wrapper fields (`name`, `enabled`) are used. |

**Outputs**

| Field | Description |
| --- | --- |
| `session_label` | Categorical label: `Asia`, `London`, `London_New_York_Overlap`, `New_York`, or `Other`. |

**Notes**
- Session boundaries follow institutional FX desk conventions (UTC-based).
- Useful for gating trades to high-liquidity periods.

---

## Market Microstructure Metrics

Measure liquidity conditions—spread tightness, tick frequency—to gate strategies to healthy market states.

### `spread` — Spread Monitoring

**YAML type:** `spread`

Tracks raw spread, spread expressed in pips, and the percentile rank within a trailing window.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `pip_size` | float | ✅ | Pip increment used to convert the spread to pips. |
| `window_seconds` | float | ✅ | Rolling horizon for percentile statistics. |

**Outputs**

| Field | Description |
| --- | --- |
| `spread` | `ask - bid` (floored at zero). |
| `spread_pips` | Spread converted into pips using `pip_size`. |
| `spread_percentile` | Fraction of ticks within the window whose spread is ≤ current spread. |

**Notes**
- Negative spreads are clipped to zero before percentile calculations.
- Percentile uses tick counts (not time-weighted). Adapt window size to desired responsiveness.

---

### `tick_rate` — Tick Throughput

**YAML type:** `tick_rate`

Counts the number of ticks observed over a sliding window and exposes derived rates.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `window_seconds` | float | ✅ | Width of the sliding window. Must be positive. |

**Outputs**

| Field | Description |
| --- | --- |
| `tick_count` | Number of ticks with timestamps > `now - window`. |
| `tick_rate_per_sec` | `tick_count / window_seconds`. |
| `tick_rate_per_min` | Tick rate expressed per minute (`tick_rate_per_sec × 60`). |

**Notes**
- Ticks with timestamps exactly on the cutoff are retained.
- Useful for throttling entry predicates during illiquid periods.

---

## Usage Tips

- Omit `enabled` or set it to `true` for active metrics; set to `false` to keep configuration templates without computing the metric.
- Names should be unique and descriptive; they become prefixes in metric snapshots (`ewma_vol_5m.vol_percentile`).
- Combine metrics with strategy predicates to filter entries/exits (e.g., require `spread_percentile < 0.5` or `z5m.z_score > 2`).
- Review the unit tests under `tests/metrics/` for concrete regression cases and edge conditions validated in CI.
