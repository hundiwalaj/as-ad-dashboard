"""Matplotlib charts for supply friction vs. inflation expectations."""

from __future__ import annotations

from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

CRISIS_START = pd.Timestamp("2021-10-01")
CRISIS_END = pd.Timestamp("2022-12-31")


def _shade_crisis(ax, start: pd.Timestamp, end: pd.Timestamp) -> None:
    ax.axvspan(start, end, color="gray", alpha=0.2, label="Supply chain peak (Q4 2021–Q4 2022)")


def plot_expectations_gap(
    quarterly: pd.DataFrame,
    monthly_gscpi: pd.Series,
    *,
    plot_start: str | datetime = "2019-01-01",
    plot_end: str | datetime = "2026-12-31",
    crisis_start: pd.Timestamp = CRISIS_START,
    crisis_end: pd.Timestamp = CRISIS_END,
    figsize: tuple[float, float] = (11, 7),
) -> plt.Figure:
    """
    Two-panel chart: GSCPI (monthly, top) and consumer vs. professional inflation
    expectations (quarterly, bottom).
    """
    t0 = pd.Timestamp(plot_start)
    t1 = pd.Timestamp(plot_end)

    gscpi = monthly_gscpi.loc[(monthly_gscpi.index >= t0) & (monthly_gscpi.index <= t1)]
    q = quarterly.loc[(quarterly.index >= t0) & (quarterly.index <= t1)]

    fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=False, constrained_layout=True)

    ax0 = axes[0]
    ax0.plot(gscpi.index, gscpi.values, color="#1f4e79", linewidth=2)
    _shade_crisis(ax0, crisis_start, crisis_end)
    ax0.set_title("Global Supply Chain Pressure Index (GSCPI)")
    ax0.set_ylabel("Standard deviations from average")
    ax0.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.5)
    ax0.grid(True, alpha=0.3)
    ax0.xaxis.set_major_locator(mdates.YearLocator())
    ax0.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax1 = axes[1]
    if "mich" in q.columns:
        ax1.plot(
            q.index,
            q["mich"],
            label="Consumer inflation expectations (MICH)",
            color="#c0392b",
            linewidth=2,
            marker="o",
            markersize=4,
        )
    if "spf_cpi_1yr" in q.columns:
        ax1.plot(
            q.index,
            q["spf_cpi_1yr"],
            label="Professional SPF 1-yr CPI forecast (median)",
            color="#27ae60",
            linewidth=2,
            marker="s",
            markersize=4,
        )
    _shade_crisis(ax1, crisis_start, crisis_end)
    ax1.set_title("Inflation expectations: consumers vs. professional forecasters")
    ax1.set_ylabel("Percent")
    ax1.set_xlabel("Date")
    ax1.legend(loc="upper left", frameon=True)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.suptitle(
        "Aggregate supply friction and the expectations gap",
        fontsize=13,
        fontweight="bold",
    )
    return fig


def plot_overlay_comparison(
    quarterly: pd.DataFrame,
    overlay_col: str,
    *,
    plot_start: str | datetime = "2018-01-01",
    plot_end: str | datetime = "2026-12-31",
    figsize: tuple[float, float] = (10, 4.5),
) -> plt.Figure:
    """Dual-axis quarterly chart: MICH vs. selected overlay (GSCPI or UMCSENT)."""
    t0 = pd.Timestamp(plot_start)
    t1 = pd.Timestamp(plot_end)
    q = quarterly.loc[(quarterly.index >= t0) & (quarterly.index <= t1)].copy()

    fig, ax_left = plt.subplots(figsize=figsize, constrained_layout=True)
    if "mich" not in q.columns or overlay_col not in q.columns:
        ax_left.text(0.5, 0.5, "Insufficient data for overlay chart", ha="center", va="center")
        return fig

    ax_left.plot(q.index, q["mich"], color="#c0392b", linewidth=2, label="MICH (inflation expectations)")
    ax_left.set_ylabel("Inflation expectations (%)", color="#c0392b")
    ax_left.tick_params(axis="y", labelcolor="#c0392b")

    ax_right = ax_left.twinx()
    overlay_label = "GSCPI (supply pressure)" if overlay_col == "gscpi" else "UMCSENT (consumer sentiment)"
    ax_right.plot(
        q.index,
        q[overlay_col],
        color="#1f4e79",
        linewidth=2,
        linestyle="--",
        label=overlay_label,
    )
    ax_right.set_ylabel(overlay_label, color="#1f4e79")
    ax_right.tick_params(axis="y", labelcolor="#1f4e79")

    if overlay_col == "gscpi":
        ax_right.axhline(0, color="#1f4e79", linewidth=0.5, linestyle=":", alpha=0.5)

    lines_l, labels_l = ax_left.get_legend_handles_labels()
    lines_r, labels_r = ax_right.get_legend_handles_labels()
    ax_left.legend(lines_l + lines_r, labels_l + labels_r, loc="upper left")
    ax_left.set_title(f"Consumer inflation expectations vs. {overlay_label}")
    ax_left.grid(True, alpha=0.3)
    ax_left.xaxis.set_major_locator(mdates.YearLocator())
    ax_left.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    return fig


def plot_macro_regimes(
    quarterly: pd.DataFrame,
    rolling_corr: pd.Series | None = None,
    *,
    plot_start: str | datetime = "2018-01-01",
    plot_end: str | datetime = "2026-12-31",
    crisis_start: pd.Timestamp = CRISIS_START,
    crisis_end: pd.Timestamp = CRISIS_END,
    figsize: tuple[float, float] = (11, 10),
) -> plt.Figure:
    """
    Multi-panel view of macro controls and sentiment across supply-shock regimes.

    Panels: GSCPI, unemployment (UNRATE), gasoline (GASREGW), UMCSENT; optional
    bottom panel for 24-month rolling GSCPI–UMCSENT correlation.
    """
    t0 = pd.Timestamp(plot_start)
    t1 = pd.Timestamp(plot_end)
    q = quarterly.loc[(quarterly.index >= t0) & (quarterly.index <= t1)].copy()

    panels: list[tuple[str, str, str]] = [
        ("gscpi", "GSCPI (supply-chain pressure)", "Standard deviations"),
        ("unrate", "Unemployment rate (UNRATE)", "Percent"),
        ("gasregw", "Retail gasoline price (GASREGW)", "USD / gallon"),
        ("umcsent", "Consumer sentiment (UMCSENT)", "Index (1966:Q1=100)"),
    ]
    nrows = len(panels) + (1 if rolling_corr is not None else 0)
    fig, axes = plt.subplots(nrows, 1, figsize=figsize, sharex=True, constrained_layout=True)
    if nrows == 1:
        axes = [axes]

    for ax, (col, title, ylabel) in zip(axes, panels):
        if col not in q.columns:
            ax.text(0.5, 0.5, f"No data for {col}", ha="center", va="center", transform=ax.transAxes)
            continue
        series = q[col].dropna()
        ax.plot(series.index, series.values, linewidth=2, color="#1f4e79")
        _shade_crisis(ax, crisis_start, crisis_end)
        if col == "gscpi":
            ax.axhline(0, color="black", linewidth=0.5, linestyle="--", alpha=0.4)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)

    if rolling_corr is not None:
        ax_corr = axes[-1]
        rc = rolling_corr.loc[(rolling_corr.index >= t0) & (rolling_corr.index <= t1)].dropna()
        ax_corr.plot(rc.index, rc.values, color="#8e44ad", linewidth=2)
        _shade_crisis(ax_corr, crisis_start, crisis_end)
        ax_corr.axhline(0, color="black", linewidth=0.5, linestyle="--", alpha=0.4)
        ax_corr.set_ylim(-1.05, 1.05)
        ax_corr.set_title("24-month rolling correlation: GSCPI vs. UMCSENT")
        ax_corr.set_ylabel("Correlation")
        ax_corr.set_xlabel("Date")
    else:
        axes[-1].set_xlabel("Date")

    for ax in axes[:-1]:
        ax.tick_params(labelbottom=False)
    axes[-1].xaxis.set_major_locator(mdates.YearLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.suptitle("Macro regimes: supply friction, prices, and labor market", fontsize=13, fontweight="bold")
    return fig
