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

"""Regression-style analysis for completed trade databases."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_EXCLUDED_FEATURE_COLUMNS = {
    "pnl_pips",
    "pnl_base",
    "cumulative_pnl",
    "entry_price",
    "exit_price",
    "signal_price",
    "timestamp_entry",
    "timestamp_exit",
    "signal_timestamp",
    "holding_seconds",
    "holding_time_seconds",
    "trade_duration_seconds",
    "duration_seconds",
}

_ENTRY_TIME_NUMERIC_FEATURE_COLUMNS = {
    "direction",
}


def _is_entry_time_predictor(column: str) -> bool:
    return column in _ENTRY_TIME_NUMERIC_FEATURE_COLUMNS or "." in column


def _numeric_feature_columns(df: pd.DataFrame, *, target_column: str) -> list[str]:
    numeric_columns: list[str] = []
    for column in df.columns:
        if column == target_column or column in _EXCLUDED_FEATURE_COLUMNS:
            continue
        if pd.api.types.is_numeric_dtype(df[column]) and _is_entry_time_predictor(column):
            numeric_columns.append(column)
    return numeric_columns


def _standardized_coefficients(design_matrix: np.ndarray, target: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    standardized = np.full(coefficients.shape, np.nan, dtype=float)
    target_std = float(np.std(target, ddof=0))
    if target_std == 0.0 or np.isnan(target_std):
        return standardized

    feature_stds = np.std(design_matrix[:, 1:], axis=0, ddof=0)
    standardized[0] = np.nan
    for idx, feature_std in enumerate(feature_stds, start=1):
        if feature_std == 0.0 or np.isnan(feature_std):
            continue
        standardized[idx] = coefficients[idx] * feature_std / target_std
    return standardized


def run_trade_regression_analysis(
    trades_path: Path | str,
    *,
    output_dir: Path | str | None = None,
    target_column: str = "pnl_pips",
) -> Path:
    """
    Run a simple multivariate linear regression over entry-time numeric trade features.

    Outputs are written to disk under ``<trades_dir>/multivariate_analysis`` by default.
    """
    resolved_trades_path = Path(trades_path).expanduser()
    if not resolved_trades_path.exists():
        raise FileNotFoundError(f"Trades file not found: {resolved_trades_path}")

    df = pd.read_parquet(resolved_trades_path)
    if df.empty:
        raise ValueError(f"Trades file {resolved_trades_path} contains no rows")
    if target_column not in df.columns:
        raise ValueError(f"Trades file missing target column: {target_column}")

    features = _numeric_feature_columns(df, target_column=target_column)
    if not features:
        raise ValueError("No eligible entry-time numeric feature columns available for regression analysis")

    working = df[[target_column, *features]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(working) < 2:
        raise ValueError("Not enough complete rows available for regression analysis")

    output_root = Path(output_dir).expanduser() if output_dir else resolved_trades_path.parent / "multivariate_analysis"
    output_root.mkdir(parents=True, exist_ok=True)

    target = working[target_column].to_numpy(dtype=float)
    predictors = working[features].to_numpy(dtype=float)
    design_matrix = np.column_stack([np.ones(len(working), dtype=float), predictors])
    feature_names = ["intercept", *features]

    coefficients, residuals, rank, singular_values = np.linalg.lstsq(design_matrix, target, rcond=None)
    fitted = design_matrix @ coefficients
    residual_vector = target - fitted
    rss = float(np.sum(residual_vector**2))
    tss = float(np.sum((target - target.mean()) ** 2))
    r_squared = float(1.0 - rss / tss) if tss > 0.0 else float("nan")

    standardized = _standardized_coefficients(design_matrix, target, coefficients)
    coefficient_frame = pd.DataFrame(
        {
            "feature": feature_names,
            "coefficient": coefficients,
            "standardized_coefficient": standardized,
        }
    )
    coefficient_frame["abs_coefficient"] = coefficient_frame["coefficient"].abs()
    coefficient_frame["abs_standardized_coefficient"] = coefficient_frame["standardized_coefficient"].abs()
    coefficient_frame.sort_values("abs_standardized_coefficient", ascending=False, na_position="last", inplace=True)

    coefficients_path = output_root / "coefficients.csv"
    coefficient_frame.to_csv(coefficients_path, index=False)

    correlation_frame = working[[target_column, *features]].corr(numeric_only=True)
    correlation_path = output_root / "correlations.csv"
    correlation_frame.to_csv(correlation_path)

    summary_path = output_root / "summary.md"
    top_features = [
        f"- `{row.feature}`: coefficient={row.coefficient:.6f}, standardized={row.standardized_coefficient:.6f}"
        for row in coefficient_frame.itertuples()
        if row.feature != "intercept" and not pd.isna(row.standardized_coefficient)
    ][:10]
    if not top_features:
        top_features = ["- No non-intercept standardized coefficients were available."]

    summary_lines = [
        "# Multivariate Trade Analysis",
        "",
        f"- **Trades file:** `{resolved_trades_path}`",
        f"- **Rows analysed:** {len(working):,}",
        f"- **Target column:** `{target_column}`",
        f"- **Predictor count:** {len(features):,}",
        f"- **Matrix rank:** {rank}",
        f"- **R-squared:** {r_squared:.6f}" if not np.isnan(r_squared) else "- **R-squared:** NaN",
        f"- **Residual sum of squares:** {rss:.6f}",
        "",
        "## Strongest Standardized Coefficients",
        "",
        *top_features,
        "",
        "## Artefacts",
        "",
        f"- `coefficients.csv`: {coefficients_path.name}",
        f"- `correlations.csv`: {correlation_path.name}",
        "",
        "This is an ordinary least squares fit over entry-time numeric predictors only.",
        "Execution-price fields, timestamps, holding-period columns, and other post-trade or identity-linked columns are excluded.",
        "Use it as a directional multivariate diagnostic, not a production model.",
    ]
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    logger.info(
        "trade regression analysis complete",
        extra={
            "trades_path": str(resolved_trades_path),
            "output_dir": str(output_root),
            "target_column": target_column,
            "features": features,
            "rank": int(rank),
            "r_squared": r_squared,
            "singular_values": singular_values.tolist(),
        },
    )
    return output_root
