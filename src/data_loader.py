"""Load and merge macro series for the Aggregate Supply & Sentiment dashboard."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INFLATION_XLSX = DATA_DIR / "Inflation.xlsx"
GSCPI_CACHE_CSV = DATA_DIR / "gscpi.csv"
GSCPI_URL = (
    "https://www.newyorkfed.org/medialibrary/research/interactives/"
    "data/gscpi/gscpi_interactive_data.csv"
)
INFLATION_URL = (
    "https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/"
    "survey-of-professional-forecasters/historical-data/Inflation.xlsx"
)
FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_START = "2018-01-01"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_fred_api_key() -> str:
    load_dotenv()
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "FRED_API_KEY is not set. Copy .env.example to .env and add your key from "
            "https://fred.stlouisfed.org/docs/api/api_key.html"
        )
    return key


def fetch_fred_series(
    series_id: str,
    start: str = DEFAULT_START,
    api_key: str | None = None,
) -> pd.Series:
    """Fetch a monthly FRED series as a float Series indexed by date."""
    api_key = api_key or get_fred_api_key()
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
        "sort_order": "asc",
    }
    response = requests.get(FRED_OBS_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    observations = payload.get("observations", [])
    if not observations:
        raise ValueError(f"No observations returned for FRED series {series_id}")

    dates = []
    values = []
    for row in observations:
        raw = row.get("value", ".")
        if raw in (".", "", None):
            continue
        dates.append(pd.Timestamp(row["date"]))
        values.append(float(raw))

    name = series_id.lower()
    series = pd.Series(values, index=pd.DatetimeIndex(dates, name="date"), name=name)
    return series.sort_index()


def fetch_fred_weekly_to_monthly(
    series_id: str,
    start: str = DEFAULT_START,
    api_key: str | None = None,
) -> pd.Series:
    """Fetch a weekly FRED series and resample to month-end means."""
    weekly = fetch_fred_series(series_id, start=start, api_key=api_key)
    if weekly.empty:
        return weekly
    monthly = weekly.resample("ME").mean()
    monthly.name = series_id.lower()
    return monthly.dropna()


def _download_if_missing(url: str, path: Path) -> None:
    if path.exists():
        return
    _ensure_data_dir()
    response = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    path.write_bytes(response.content)


def load_spf_inflation(path: Path | None = None) -> pd.DataFrame:
    """
    Load Philadelphia Fed SPF 1-year-ahead CPI inflation (median, INFCPI1YR).

    Returns quarterly DataFrame with columns: year, quarter, quarter_end, spf_cpi_1yr.
    """
    path = path or INFLATION_XLSX
    _download_if_missing(INFLATION_URL, path)

    raw = pd.read_excel(path, engine="calamine")
    raw.columns = [str(c).strip().upper() for c in raw.columns]

    required = {"YEAR", "QUARTER", "INFCPI1YR"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Inflation.xlsx missing columns {missing}; found {list(raw.columns)}")

    df = raw[["YEAR", "QUARTER", "INFCPI1YR"]].copy()
    df = df.rename(columns={"INFCPI1YR": "spf_cpi_1yr"})
    df["year"] = pd.to_numeric(df["YEAR"], errors="coerce").astype("Int64")
    df["quarter"] = pd.to_numeric(df["QUARTER"], errors="coerce").astype("Int64")
    df["spf_cpi_1yr"] = pd.to_numeric(df["spf_cpi_1yr"], errors="coerce")
    df = df.dropna(subset=["year", "quarter"])
    df["year"] = df["year"].astype(int)
    df["quarter"] = df["quarter"].astype(int)
    period = df["year"].astype(str) + "Q" + df["quarter"].astype(str)
    df["quarter_end"] = pd.PeriodIndex(period, freq="Q").to_timestamp(how="end")
    df = df.drop(columns=["YEAR", "QUARTER"])
    df = df.dropna(subset=["spf_cpi_1yr"])
    return df.sort_values("quarter_end").reset_index(drop=True)


def fetch_gscpi_monthly(
    start: str = DEFAULT_START,
    cache_path: Path | None = None,
) -> pd.Series:
    """
    Load NY Fed Global Supply Chain Pressure Index (monthly).

    Uses the latest vintage column from the official interactive CSV, with optional
    local cache at data/gscpi.csv.
    """
    cache_path = cache_path or GSCPI_CACHE_CSV
    _ensure_data_dir()

    if not cache_path.exists():
        response = requests.get(GSCPI_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        cache_path.write_bytes(response.content)

    wide = pd.read_csv(cache_path, encoding="utf-8-sig")
    if "Date" not in wide.columns:
        raise ValueError("GSCPI CSV missing Date column")

    value_cols = [c for c in wide.columns if c != "Date"]
    if not value_cols:
        raise ValueError("GSCPI CSV has no value columns")

    latest_col = value_cols[-1]
    slim = wide[["Date", latest_col]].copy()
    slim = slim.dropna(subset=[latest_col])
    slim["date"] = pd.to_datetime(slim["Date"], format="mixed", dayfirst=False)
    series = pd.Series(
        pd.to_numeric(slim[latest_col], errors="coerce").values,
        index=pd.DatetimeIndex(slim["date"]),
        name="gscpi",
    )
    series = series.dropna().sort_index()
    series = series[series.index >= pd.Timestamp(start)]
    return series


def _monthly_to_quarterly(series: pd.Series) -> pd.Series:
    """Resample monthly observations to quarter-end means."""
    if series.empty:
        return series
    quarterly = series.resample("QE").mean()
    quarterly.name = series.name
    return quarterly


def build_master_frame(
    start: str = DEFAULT_START,
    api_key: str | None = None,
) -> pd.DataFrame:
    """
    Build a quarterly merged DataFrame from SPF, FRED, and NY Fed sources.

    Columns include spf_cpi_1yr, gscpi, mich, umcsent, gasregw (weekly gasoline
    prices averaged to monthly, then to quarterly), and unrate (civilian unemployment).
    Index: quarter-end DatetimeIndex.
    """
    spf = load_spf_inflation()
    spf_q = spf.set_index("quarter_end")[["spf_cpi_1yr"]]

    gscpi_m = fetch_gscpi_monthly(start=start)
    mich_m = fetch_fred_series("MICH", start=start, api_key=api_key)
    umcsent_m = fetch_fred_series("UMCSENT", start=start, api_key=api_key)
    gasregw_m = fetch_fred_weekly_to_monthly("GASREGW", start=start, api_key=api_key)
    unrate_m = fetch_fred_series("UNRATE", start=start, api_key=api_key)

    gscpi_q = _monthly_to_quarterly(gscpi_m).to_frame()
    mich_q = _monthly_to_quarterly(mich_m).to_frame()
    umcsent_q = _monthly_to_quarterly(umcsent_m).to_frame()
    gasregw_q = _monthly_to_quarterly(gasregw_m).to_frame()
    unrate_q = _monthly_to_quarterly(unrate_m).to_frame()

    quarterly = (
        spf_q.join(gscpi_q, how="outer")
        .join(mich_q, how="outer")
        .join(umcsent_q, how="outer")
        .join(gasregw_q, how="outer")
        .join(unrate_q, how="outer")
    )
    quarterly = quarterly.sort_index()
    quarterly = quarterly.loc[quarterly.index >= pd.Timestamp(start)]
    quarterly = quarterly.interpolate(method="time", limit_direction="both", limit=2)
    quarterly.index.name = "quarter_end"
    return quarterly


def fetch_monthly_for_plots(
    start: str = DEFAULT_START,
    api_key: str | None = None,
) -> dict[str, pd.Series]:
    """Return monthly series used in charts (GSCPI panel uses monthly frequency)."""
    return {
        "gscpi": fetch_gscpi_monthly(start=start),
        "mich": fetch_fred_series("MICH", start=start, api_key=api_key),
        "umcsent": fetch_fred_series("UMCSENT", start=start, api_key=api_key),
        "gasregw": fetch_fred_weekly_to_monthly("GASREGW", start=start, api_key=api_key),
        "unrate": fetch_fred_series("UNRATE", start=start, api_key=api_key),
    }
