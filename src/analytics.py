"""Rolling correlation and Granger causality analytics on the master macro frame."""

from __future__ import annotations

from typing import Any

import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests

GSCPI_COL = "gscpi"
UMCSENT_COL = "umcsent"
MICH_COL = "mich"
DEFAULT_ROLLING_MONTHS = 24
DEFAULT_MAX_LAG = 3


def _infer_months_per_period(index: pd.DatetimeIndex) -> float:
    """Approximate months per observation from median index spacing."""
    if len(index) < 2:
        return 1.0
    deltas = pd.Series(index).diff().dropna().dt.days.median()
    if deltas <= 0:
        return 1.0
    return max(1.0, deltas / 30.4375)


def rolling_correlation_gscpi_umcsent(
    df: pd.DataFrame,
    window_months: int = DEFAULT_ROLLING_MONTHS,
    min_periods: int | None = None,
) -> pd.Series:
    """
    Rolling correlation between GSCPI and UMCSENT.

    Uses a 24-month window on monthly data. On quarterly master frames, the window
    is converted to eight quarters (24 months). NaNs are dropped pairwise before
    each rolling window is evaluated.
    """
    pair = df[[GSCPI_COL, UMCSENT_COL]].copy()
    pair = pair.dropna(how="any")
    if pair.empty:
        raise ValueError("No overlapping observations for gscpi and umcsent.")

    months_per = _infer_months_per_period(pair.index)
    window = max(2, int(round(window_months / months_per)))
    if min_periods is None:
        min_periods = max(2, window // 2)

    rolling = pair[GSCPI_COL].rolling(window=window, min_periods=min_periods).corr(pair[UMCSENT_COL])
    rolling.name = f"roll_corr_{GSCPI_COL}_{UMCSENT_COL}_{window_months}m"
    return rolling


def granger_gscpi_causes_mich(
    df: pd.DataFrame,
    max_lag: int = DEFAULT_MAX_LAG,
) -> dict[int, float]:
    """
    Test whether GSCPI Granger-causes MICH (consumer inflation expectations).

    Returns p-values from the SSR F-test for lags 1 through max_lag. Rows with
    missing values in either series are dropped before estimation.
    """
    if max_lag < 1:
        raise ValueError("max_lag must be at least 1.")

    pair = df[[MICH_COL, GSCPI_COL]].dropna(how="any")
    if len(pair) <= max_lag + 2:
        raise ValueError(
            f"Need more than {max_lag + 2} joint observations for Granger test; got {len(pair)}."
        )

    results: dict[int, Any] = grangercausalitytests(
        pair[[MICH_COL, GSCPI_COL]],
        maxlag=max_lag,
        verbose=False,
    )
    return {lag: float(results[lag][0]["ssr_ftest"][1]) for lag in range(1, max_lag + 1)}


def format_granger_summary(
    pvalues: dict[int, float],
    *,
    cause: str = GSCPI_COL,
    effect: str = MICH_COL,
    alpha: float = 0.05,
) -> str:
    """Academic-style text summary of Granger causality p-values."""
    lines = [
        "Granger causality test (SSR F-test, H0: lagged "
        f"{cause.upper()} does not help predict {effect.upper()})",
        f"Specification: {effect.upper()} on lagged {effect.upper()} and lagged {cause.upper()}.",
        "",
    ]
    for lag, pval in sorted(pvalues.items()):
        reject = pval < alpha
        conclusion = "reject H0" if reject else "fail to reject H0"
        lines.append(
            f"  Lag {lag}: p = {pval:.4f}  →  {conclusion} at {alpha:.0%} "
            f"({'significant' if reject else 'not significant'} predictive content from {cause.upper()})."
        )
    lines.append("")
    any_sig = any(p < alpha for p in pvalues.values())
    if any_sig:
        lines.append(
            f"Summary: At least one lag provides evidence that {cause.upper()} "
            f"Granger-causes {effect.upper()}."
        )
    else:
        lines.append(
            f"Summary: No lag up to {max(pvalues)} provides statistically significant "
            f"evidence that {cause.upper()} Granger-causes {effect.upper()} at {alpha:.0%}."
        )
    return "\n".join(lines)
