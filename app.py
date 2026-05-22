"""Interactive Streamlit dashboard: Aggregate Supply & Consumer Sentiment."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.data_loader import build_master_frame, fetch_monthly_for_plots
from src.plots import plot_expectations_gap, plot_overlay_comparison

load_dotenv()

st.set_page_config(
    page_title="Aggregate Supply & Sentiment",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(ttl=3600, show_spinner="Loading macro data…")
def get_quarterly_data():
    return build_master_frame()


@st.cache_data(ttl=3600, show_spinner="Loading monthly series…")
def get_monthly_data():
    return fetch_monthly_for_plots()


def main() -> None:
    st.title("Aggregate Supply & Consumer Sentiment Dashboard")
    st.markdown(
        "This dashboard maps **supply-chain friction** (NY Fed GSCPI) into "
        "**consumer inflation expectations** (FRED MICH) and contrasts them with "
        "**professional forecaster expectations** (Philadelphia Fed SPF), alongside "
        "**consumer sentiment** (FRED UMCSENT)."
    )

    try:
        quarterly = get_quarterly_data()
        monthly = get_monthly_data()
    except ValueError as exc:
        st.error(str(exc))
        st.info("Create a `.env` file with `FRED_API_KEY=...` (see `.env.example`).")
        return
    except Exception as exc:
        st.error(f"Failed to load data: {exc}")
        return

    if quarterly.empty:
        st.warning("No data available for the selected range.")
        return

    min_date = quarterly.index.min().date()
    max_date = quarterly.index.max().date()

    st.sidebar.header("Controls")
    date_range = st.sidebar.slider(
        "Date range",
        min_value=min_date,
        max_value=max_date,
        value=(max(min_date, quarterly.index.min().replace(year=2018).date()), max_date),
        format="YYYY-MM-DD",
    )
    overlay_choice = st.sidebar.selectbox(
        "Primary overlay (secondary chart)",
        options=[
            "Consumer Sentiment (UMCSENT)",
            "Supply Chain Pressure (GSCPI)",
        ],
    )
    overlay_col = "umcsent" if "Sentiment" in overlay_choice else "gscpi"

    plot_start = str(date_range[0])
    plot_end = str(date_range[1])

    st.subheader("Friction vs. expectations")
    fig_gap = plot_expectations_gap(
        quarterly,
        monthly["gscpi"],
        plot_start=plot_start,
        plot_end=plot_end,
    )
    st.pyplot(fig_gap)

    st.subheader("Overlay comparison")
    fig_overlay = plot_overlay_comparison(
        quarterly,
        overlay_col,
        plot_start=plot_start,
        plot_end=plot_end,
    )
    st.pyplot(fig_overlay)

    mask = (quarterly.index.date >= date_range[0]) & (quarterly.index.date <= date_range[1])
    st.subheader("Quarterly data (latest rows)")
    st.dataframe(
        quarterly.loc[mask].tail(20).reset_index(),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
