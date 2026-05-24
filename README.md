# Aggregate Supply & Consumer Sentiment Dashboard

Empirical dashboard linking **aggregate supply friction** (NY Fed Global Supply Chain Pressure Index), **consumer inflation expectations** and **sentiment** (FRED), and **professional forecaster CPI expectations** (Philadelphia Fed Survey of Professional Forecasters).

## Setup

```bash
pip install -r requirements.txt
```

1. Register a free API key at [FRED API Keys](https://fred.stlouisfed.org/docs/api/api_key.html).
2. Copy `.env.example` to `.env` and set `FRED_API_KEY`.
3. On first run, `Inflation.xlsx` and `gscpi.csv` are downloaded into `data/` if missing.

## Usage

**Jupyter notebook** — open `dashboard.ipynb` and run all cells.

**Streamlit app**:

```bash
streamlit run app.py
```

## Data sources

| Series | Source | Frequency |
|--------|--------|-----------|
| GSCPI | [NY Fed GSCPI](https://www.newyorkfed.org/research/policy/gscpi) interactive CSV | Monthly |
| MICH | [FRED MICH](https://fred.stlouisfed.org/series/MICH) | Monthly |
| UMCSENT | [FRED UMCSENT](https://fred.stlouisfed.org/series/UMCSENT) | Monthly |
| GASREGW | [FRED GASREGW](https://fred.stlouisfed.org/series/GASREGW) | Weekly → monthly mean → quarterly |
| UNRATE | [FRED UNRATE](https://fred.stlouisfed.org/series/UNRATE) | Monthly |
| SPF 1-yr CPI | [Philadelphia Fed Inflation.xlsx](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/inflation-forecasts) (`INFCPI1YR`) | Quarterly |

Monthly FRED and GSCPI series are resampled to **quarter-end means** before merging with SPF.

## Project layout

- `src/data_loader.py` — fetch, resample, merge
- `src/plots.py` — matplotlib figures
- `src/analytics.py` — rolling correlation and Granger causality tests
- `dashboard.ipynb` — analysis notebook
- `app.py` — Streamlit UI

## Citations

- Federal Reserve Bank of New York, Global Supply Chain Pressure Index
- Surveys of Consumers, University of Michigan (MICH, UMCSENT via FRED)
- Federal Reserve Bank of Philadelphia, Survey of Professional Forecasters
