# Module 4 Assignment — Time Series Analysis (Traffic Prediction & Anomaly Detection)

Repository for Ontario Tech course **ENGR 5785G — Real-Time Data Analytics IoT**.

Student: Vitor Brandao Raposo

Student ID: 101011969

Date: 06/2026

---

## Quick Start (Windows)

```powershell
# 1. Activate the project virtual environment (from assignment_4/)
..\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch Jupyter and open the notebook
jupyter notebook Raposo_Vitor_TimeSeries.ipynb
```

The first cell downloads `PeMSD7_V_228.csv` from the public STGCN benchmark
repo and caches it to `data/` — no manual download step.

To run the whole notebook from the command line (the grader's
"runs top-to-bottom without errors" check):

```powershell
jupyter nbconvert --to notebook --execute Raposo_Vitor_TimeSeries.ipynb --output Raposo_Vitor_TimeSeries.ipynb
```

---

## Repository Structure

```text
assignment_4/
├── ENGR500G_Time_Series_Analysis_Assignment.pdf   ← Assignment spec (6 pages + rubric)
├── Raposo_Vitor_TimeSeries.ipynb                  ← The deliverable
├── data/
│   └── PeMSD7_V_228.csv                           ← Downloaded by Cell 1, gitignored
├── report/
│   └── report.md                                  ← 2–4 page write-up
├── figures/                                       ← Saved plots from the notebook (gitignored)
├── requirements.txt                               ← pandas, numpy, matplotlib, scikit-learn, statsmodels, jupyter
├── .gitignore
└── README.md                                      ← This file
```

The notebook is organized to match the rubric one-to-one. Each task is a
level-2 markdown heading with the exact rubric label so the grader can find
it with Ctrl-F.

| Cell | Section                                                         | Marks |
| ---- | --------------------------------------------------------------- | ----- |
| 1    | Setup (imports + dataset download)                              | —     |
| 2    | `## Task 1 — Data Loading and Initial Exploration`              | 15    |
| 3    | `## Task 2 — Preprocessing and Feature Engineering`             | 15    |
| 4    | `## Task 3 — Classical Forecasting Model: SARIMA`               | 20    |
| 5    | `## Task 4 — Machine-Learning Forecasting Model: Random Forest` | 20    |
| 6    | `## Task 5 — Residual-Based Anomaly Detection`                  | 15    |
| 7    | `## Summary — Model Comparison Table`                           | —     |

The report (Task 6, 15 marks) lives in `report/report.md` — drafted from
the notebook outputs and exported to PDF before submission.

---

## Dataset

Source: PeMSD7 traffic-speed benchmark from the public STGCN repository.

- URL: <https://github.com/VeritasYin/STGCN_IJCAI-18/raw/master/dataset/PeMSD7_V_228.csv>
- Shape: 12,672 rows × 228 sensors (5-minute aggregation, ~44 days)
- One sensor column (`sensor_id=0`) is used as the target series

A synthetic 5-minute `DatetimeIndex` starting `2012-05-01` is built in Cell 2
because the raw CSV does not include timestamps. This is allowed by the
assignment spec.

> **Submission rule:** the CSV is **gitignored** and **must not be submitted**.
> Cell 1 downloads it automatically on first run.

---

## Task 1 — Data Loading and Initial Exploration (15 pts)

Cell `## Task 1`.

- Pick sensor 0 as the target series
- Attach a 5-min `DatetimeIndex` starting 2012-05-01
- Plot the first 3 days of raw speeds
- Report mean, median, std, min, max, and missing-value count
- Short discussion of the daily pattern and rush-hour drops

---

## Task 2 — Preprocessing and Feature Engineering (15 pts)

Cell `## Task 2`.

- `interpolate().ffill().bfill()` on the speed column
- Lag features for lags **1, 2, 3, 6, 12** (5-min steps)
- Rolling **mean** and **std** for windows **6, 12, 24** (i.e., 30-min, 1-h, 2-h)
- Calendar features: `hour`, `dayofweek`, `is_weekend`
- Target: speed **15 minutes ahead** (`shift(-3)`)

---

## Task 3 — Classical Forecasting Model: SARIMA (20 pts)

Cell `## Task 3`.

- The series is **resampled to hourly means for SARIMA only** (`m=24` instead
  of `m=288`). The `m=288` state-space fit was infeasible on a laptop —
  each Kalman pass took over 30 minutes. Random Forest and the persistence
  baseline still use the native 5-minute resolution.
- Chronological 80/20 split on the hourly series; test horizon = 24 hours
- Training capped to the last 21 days (504 hourly points)
- Model: `SARIMAX(order=(1,1,1), seasonal_order=(0,1,1,24))`
- Reports MAE and RMSE
- Markdown cell explains the resampling choice and why this order was chosen

---

## Task 4 — Machine-Learning Forecasting Model: Random Forest (20 pts)

Cell `## Task 4`.

- Chronological 80/20 split on the engineered feature matrix
- Persistence baseline: `target = current speed`
- Model: `RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)`
- Reports MAE, RMSE, and MAPE for both baseline and Random Forest
- Actual-vs-predicted plot for one day (288 points) of the test set

---

## Task 5 — Residual-Based Anomaly Detection (15 pts)

Cell `## Task 5`.

- Residual = actual − Random Forest prediction
- Threshold = 99th percentile of `|residual|` on the test window
- Lists the top 10 anomalies sorted by absolute residual
- Plots the test window with anomalies marked
- Short interpretation of what the anomalies likely represent

---

## Task 6 — Report (15 pts)

File: `report/report.md` — 2 to 4 pages, exported to PDF before submission.

Sections:

1. Introduction
2. Data and preprocessing
3. Methods (baseline, SARIMA, Random Forest, anomaly threshold)
4. Results (comparison table + figures)
5. Discussion (best model, two limitations, one real-time deployment idea)
6. References

To export the markdown to PDF:

```powershell
# Option A — VS Code "Markdown PDF" extension: right-click report.md → Export (pdf)
# Option B — pandoc
pandoc report/report.md -o report/report.pdf
```

---

## Running the Notebook End-to-End

The grader's reproducibility check is a single command:

```powershell
jupyter nbconvert --to notebook --execute Raposo_Vitor_TimeSeries.ipynb --output Raposo_Vitor_TimeSeries.ipynb
```

Exit code `0` and no traceback cells = "runs top-to-bottom without errors".

Expected runtime is about a minute. The first run also downloads the ~29 MB
`PeMSD7_Full.zip` and extracts `PeMSD7_V_228.csv` from it (~5 s).

---

## Submission Checklist (from PDF page 5)

Before submitting on Canvas, confirm:

- [ ] Notebook runs top-to-bottom without errors (`jupyter nbconvert --execute` exits 0)
- [ ] `data/PeMSD7_V_228.csv` is **NOT** in the submission (gitignored, sourced from GitHub)
- [ ] Short report exported to PDF — 2 to 4 pages excluding appendix
- [ ] At least three figures present: raw time series, actual-vs-predicted, anomaly plot
- [ ] At least one model comparison table (Persistence / SARIMA / Random Forest)
- [ ] Brief written explanation of preprocessing, model choice, and results
- [ ] All external sources and the PeMSD7 dataset cited in the report

**Academic integrity:** AI-assisted coding tools are allowed per the PDF, but
the written analyses must be understood and reproducible.
