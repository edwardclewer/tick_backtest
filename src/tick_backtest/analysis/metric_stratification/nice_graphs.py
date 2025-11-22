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

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def _auto_edges(values: np.ndarray,
                mode: str = "fixed",                 # "fixed"|"fd"|"scott"|"sigma"|"nbins"
                nbins: int | None = None,            # used when mode="nbins"
                width: float | None = None,          # used when mode="fixed"
                sigma_width: float = 0.25,           # bin width as multiple of sigma when mode="sigma"
                sigma_span: float = 4.0,             # plot range ±Kσ when mode="sigma"
                clip_quantiles: tuple[float,float] = (0.001, 0.999),  # drop extreme outliers
                hard_cap_bins: tuple[int,int] = (20, 400)             # safety bounds for bin count
                ):
    """Return bin edges for 1D binning."""
    v = values[np.isfinite(values)]
    # Range limit to avoid pathological tails
    lo, hi = np.quantile(v, clip_quantiles[0]), np.quantile(v, clip_quantiles[1])
    v = v[(v >= lo) & (v <= hi)]
    n = len(v)
    if n == 0:
        raise ValueError("No finite values after clipping.")

    v_min, v_max = float(v.min()), float(v.max())
    span = v_max - v_min
    if span == 0:
        return np.array([v_min, v_max])

    if mode == "fixed":
        if width is None:
            # fall back to Scott as a sane default for normal-ish data
            std = float(v.std(ddof=1))
            width = max(3.5 * std / (n ** (1/3)), span / 200)
        nb = int(np.clip(np.ceil(span / width), *hard_cap_bins))
        edges = np.linspace(v_min, v_max, nb + 1)

    elif mode == "fd":  # Freedman–Diaconis (robust to tails)
        q75, q25 = np.percentile(v, [75, 25])
        iqr = max(q75 - q25, np.finfo(float).eps)
        width = 2 * iqr / (n ** (1/3))
        nb = int(np.clip(np.ceil(span / width), *hard_cap_bins))
        edges = np.linspace(v_min, v_max, nb + 1)

    elif mode == "scott":  # Normal reference
        std = float(v.std(ddof=1))
        width = max(3.5 * std / (n ** (1/3)), span / 200)
        nb = int(np.clip(np.ceil(span / width), *hard_cap_bins))
        edges = np.linspace(v_min, v_max, nb + 1)

    elif mode == "sigma":  # bins on σ-grid, easy to interpret
        mu, std = float(v.mean()), float(v.std(ddof=1))
        if std == 0:
            edges = np.array([v_min, v_max])
        else:
            lo_s, hi_s = mu - sigma_span * std, mu + sigma_span * std
            width = std * sigma_width
            nb = int(np.clip(np.ceil((hi_s - lo_s) / width), *hard_cap_bins))
            edges = np.linspace(lo_s, hi_s, nb + 1)

    elif mode == "nbins":
        nb = int(np.clip(nbins if nbins else 100, *hard_cap_bins))
        edges = np.linspace(v_min, v_max, nb + 1)

    else:
        raise ValueError(f"Unknown mode: {mode}")

    return edges


def _merge_bins_to_min_count(edges: np.ndarray, x: np.ndarray, min_count: int) -> np.ndarray:
    """
    Optional: adaptively merge adjacent bins left -> right until each has >= min_count.
    This sacrifices fixed width but keeps a readable curve in sparse tails.
    """
    counts, _ = np.histogram(x, bins=edges)
    new_edges = [edges[0]]
    acc = 0
    for i, c in enumerate(counts):
        acc += c
        if acc >= min_count:
            new_edges.append(edges[i+1])
            acc = 0
    if new_edges[-1] != edges[-1]:
        new_edges.append(edges[-1])
    return np.array(new_edges)


def stratify_metric(
    df: pd.DataFrame,
    *,
    metric: str,
    value_col: str = "pnl_pips",
    mode: str = "scott",
    nbins: int | None = None,
    width: float | None = None,
    sigma_width: float = 0.25,
    sigma_span: float = 4.0,
    clip_quantiles: tuple[float, float] = (0.001, 0.999),
    min_count: int = 100,
    merge_to_min_count: bool = False,
    smoothing_window: int = 5,
    plot: bool = True,
    style: str = "bars",
    show_counts: bool = True,
    counts_logscale: bool = False,
    zero_line: bool = True,
    xlim_quantiles: tuple[float, float] | None = (0.005, 0.995),
    drop_plot_width_outliers: float | None = 10.0,
    title: str | None = None,
    save_graph_path: str | Path | None = None,
    save_csv_path: str | Path | None = None,
) -> pd.DataFrame:

    assert metric in df.columns, f"Missing column: {metric}"
    x = df[metric].to_numpy()
    y = df[value_col].to_numpy()
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) == 0:
        raise ValueError("No finite data for metric/value.")

    # 1) Edges (same logic as before)
    edges = _auto_edges(x, mode=mode, nbins=nbins, width=width,
                        sigma_width=sigma_width, sigma_span=sigma_span,
                        clip_quantiles=clip_quantiles)
    if merge_to_min_count:
        edges = _merge_bins_to_min_count(edges, x, min_count)

    # 2) Bin + aggregate
    cats = pd.cut(x, bins=edges, include_lowest=True)
    df_b = pd.DataFrame({"bin": cats, "x": x, "y": y})
    g = df_b.groupby("bin", observed=True)

    summary = g.agg(
        count=("y", "size"),
        avg_pnl=("y", "mean"),
        std_pnl=("y", "std"),
        median_pnl=("y", "median"),
        win_rate=("y", lambda s: (s > 0).mean())
    ).reset_index()

    summary["bin_left"]   = summary["bin"].apply(lambda iv: iv.left).astype(float)
    summary["bin_right"]  = summary["bin"].apply(lambda iv: iv.right).astype(float)
    summary["bin_center"] = 0.5 * (summary["bin_left"] + summary["bin_right"])
    summary["bin_width"]  = summary["bin_right"] - summary["bin_left"]

    # EV CI (normal approx)
    n_eff = summary["count"].clip(lower=1)
    summary["se"] = summary["std_pnl"] / np.sqrt(n_eff)
    z = 1.96
    summary["ev_lo"] = summary["avg_pnl"] - z * summary["se"]
    summary["ev_hi"] = summary["avg_pnl"] + z * summary["se"]

    # 3) Filter for reliability
    shown = summary.query("count >= @min_count").copy()

    # 4) Optional: drop extreme plot-width outliers (kept in CSV)
    if drop_plot_width_outliers is not None and not shown.empty:
        med_w = shown["bin_width"].median()
        shown = shown[shown["bin_width"] <= drop_plot_width_outliers * med_w]

    graph_path = Path(save_graph_path).expanduser() if save_graph_path else None
    csv_path = Path(save_csv_path).expanduser() if save_csv_path else None
    if graph_path:
        graph_path.parent.mkdir(parents=True, exist_ok=True)
    if csv_path:
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    # 5) Plot
    if plot:
        fig, ax1 = plt.subplots(figsize=(9,4))

        if style == "bars":
            # --- CI gray background band (before bars so it sits behind) ---
            if "ev_lo" in shown and "ev_hi" in shown:
                # Sort by bin_center to ensure proper fill path
                s = shown.sort_values("bin_center")
                ax1.fill_between(
                    s["bin_center"], s["ev_lo"], s["ev_hi"],
                    color="gray", alpha=0.15, zorder=1
                )

            # --- Bars on top of shaded CI band ---
            ax1.bar(
                shown["bin_left"], shown["avg_pnl"],
                width=shown["bin_width"], align="edge",
                alpha=0.85, edgecolor="black", linewidth=0.3, zorder=2
            )
            # Optional CI as thin vertical lines at bin centers
            ax1.vlines(shown["bin_center"], shown["ev_lo"], shown["ev_hi"], alpha=0.35, linewidth=0.8)
        else:
            # Line/points if you prefer (kept for completeness)
            ax1.scatter(shown["bin_center"], shown["avg_pnl"], s=12, alpha=0.7)
            if smoothing_window and smoothing_window > 1:
                smoothed = shown["avg_pnl"].rolling(smoothing_window, center=True).mean()
                ax1.plot(shown["bin_center"], smoothed, linewidth=1.5)
            ax1.fill_between(shown["bin_center"], shown["ev_lo"], shown["ev_hi"], alpha=0.12, linewidth=0)

        ax1.set_xlabel(metric)
        ax1.set_ylabel("avg_pnl (pips)")
        if zero_line:
            ax1.axhline(0.0, linestyle="--", linewidth=1.0, alpha=0.7)

        # Axis clipping to avoid one giant tail bin squashing the rest
        if xlim_quantiles is not None and not shown.empty:
            lo, hi = np.quantile(shown["bin_center"], xlim_quantiles)
            ax1.set_xlim(lo, hi)

        # Counts overlay as a step curve on twin axis (kept linear by default)
        if show_counts and not shown.empty:
            ax2 = ax1.twinx()
            # Build a step shape using bin edges
            step_x = np.r_[shown["bin_left"].to_numpy(), shown["bin_right"].iloc[-1]]
            step_y = np.r_[shown["count"].to_numpy(), shown["count"].iloc[-1]]
            ax2.step(step_x, step_y, where="post", alpha=0.45, linewidth=1.2)
            ax2.set_ylabel("Count")
            if counts_logscale:
                ax2.set_yscale("log")
            if not counts_logscale:
                ax2.set_ylim(bottom=0)

        ax1.set_title(title or f"{metric} – {mode} bins (min_count={min_count})")
        ax1.grid(True, alpha=0.25)
        fig.tight_layout()

        if graph_path:
            plt.savefig(graph_path, dpi=140)
            plt.close(fig)
        else:
            plt.show()

    # 6) Save outputs: CSV + Markdown table
    if csv_path:
        summary.to_csv(csv_path, index=False)


    return summary
