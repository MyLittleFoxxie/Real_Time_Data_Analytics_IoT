# Real_Time_Data_Analytics_IoT

Repository for Ontario Tech course **202605 — Real-Time Data Analytics IoT**.
Student: Vitor Brandao Raposo
Student ID: 101011969

---

## Assignment 1 — Real-Time Streaming Engine

Demo link: <https://youtu.be/9Ra1tTJrD8g>

ENGR 5785G Assignment 1. End-to-end Kafka pipeline that replays hourly weather observations as a live
stream, runs an offline-trained regression model in a Faust streams app, and prints predictions from a
downstream consumer.

All assignment files live in [assignment_1/](assignment_1/). The instructions below assume you `cd assignment_1`
before running anything.

### Stack

- **Streams library:** `faust-streaming` (Python). Chosen because the assignment lists it as Option A and
  it lets us define the topology declaratively with `@app.agent`, not a plain consumer loop.
- **Kafka:** single-broker local cluster via Docker Compose.
- **ML model:** `scikit-learn` `LinearRegression`, trained offline. Random Forest fit alongside for comparison.

### Dataset

Hourly observations from **Toronto City** (Climate ID `6158355`) — Environment and Climate Change Canada,
[climate.weather.gc.ca](https://climate.weather.gc.ca/historical_data/search_historic_data_e.html).

The 11 CSVs in [assignment_1/data/](assignment_1/data/) cover **May of each year 2016 → 2026**:

```
en_climate_hourly_ON_6158355_05-2016_P1H.csv
en_climate_hourly_ON_6158355_05-2017_P1H.csv
...
en_climate_hourly_ON_6158355_05-2026_P1H.csv
```

**How the files are used:**

| Component                              | Files                                        | Why                                                               |
| -------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------- |
| `train_model.ipynb` (offline training) | **all 11** via `load_all()`                  | More training data. Most-recent year is held out as the test set. |
| `src/producer.py` (live replay)        | **only the most recent** via `load_latest()` | Streams data the model has _not_ trained on (clean demo).         |

**Columns consumed from each CSV:**

- `Date/Time (LST)` → timestamp + `hour`
- `Temp (°C)` → `temp`
- `Dew Point Temp (°C)` → `dew_point`
- `Rel Hum (%)` → `humidity`
- `Stn Press (kPa)` → `pressure`

`Wind Spd (km/h)` is **not** used: Toronto City station 6158355 does not report wind, so every row is
flagged `M` / empty. Including it would drop the entire dataset. Missing values elsewhere are coerced to
NaN and the row is dropped — see [assignment_1/src/data_loader.py](assignment_1/src/data_loader.py).

**Target:** next-hour temperature (regression). A directional label (`1` if predicted next-hour temp >
current, else `0`) is derived from the regressor's output so accuracy + F1 can be reported alongside
RMSE / R².

**Adding more data:** drop additional `en_climate_hourly_*.csv` files into `assignment_1/data/`. They
are picked up automatically by `load_all()` (training) and the newest by `load_latest()` (producer).

### Architecture

```
data/en_climate_hourly_*.csv
       |
       v
  producer.py  ---publish--->  [raw-weather]  ---consume--->  streams_app.py
   ~1 row/sec                                                       |
                                                                    v
                                                              model.joblib
                                                                    |
                                                                    v
                                                            [predictions]
                                                                    |
                                                                    v
                                                              consumer.py
                                                                (stdout)
```

### Setup

Prerequisites: Docker Desktop, Python 3.11 (Faust-streaming has known issues on 3.12+).
**All commands below assume your working directory is `assignment_1/`.**

```powershell
# 0. cd into the assignment folder
cd assignment_1

# 1. create a Python 3.11 venv (uv shown; replace with `python -m venv` if not using uv)
uv python install 3.11
uv venv --python 3.11
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt

# 2. start Kafka + Zookeeper
docker compose up -d
docker compose ps      # both should be healthy

# 3. train the model offline
jupyter nbconvert --to notebook --execute train_model.ipynb --output train_model.ipynb
# produces model.joblib in assignment_1/
```

### Run (three terminals)

**Terminal 1 — Streams processor (start first so it doesn't miss messages):**

```powershell
.\.venv\Scripts\Activate.ps1
cd .\assignment_1\
faust -A src.streams_app worker -l info
```

**Terminal 2 — Output consumer:**

```powershell
.\.venv\Scripts\Activate.ps1
cd .\assignment_1\
python -m src.consumer
```

**Terminal 3 — Producer (drives the demo):**

```powershell
.\.venv\Scripts\Activate.ps1
cd .\assignment_1\
python -m src.producer
```

Each producer message takes ~1 second; the Faust agent transforms it and emits a prediction, and the
consumer prints something like:

```
[2024-01-12T14:00:00] temp= 1.40C  ->  next_hour= 1.62C  (delta=+0.22, UP)
```

Tail the topics directly if you want to verify:

```powershell
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw-weather --from-beginning --max-messages 3
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic predictions --from-beginning --max-messages 3
```

### Model performance

Trained on Mays 2016–2025 (7,415 hourly rows). Tested on May 2026 (479 hourly rows held out chronologically).

| Model            | RMSE (°C) | R²    | Accuracy (direction) | F1 (direction) |
| ---------------- | --------- | ----- | -------------------- | -------------- |
| LinearRegression | 1.037     | 0.966 | 0.599                | 0.549          |
| RandomForest     | 0.892     | 0.975 | 0.729                | 0.698          |

RMSE and R² are the regression metrics. The direction label lets us also report accuracy + F1 as the
rubric asks. The deployed model is `LinearRegression` (saved as `model.joblib`).

### Demo video

Link: _add YouTube/Drive URL here_

### Repo layout

```
assignment_1/
├── docker-compose.yml          single-broker Kafka + Zookeeper
├── requirements.txt
├── train_model.ipynb           offline training, writes model.joblib
├── model.joblib                trained model artifact (committed)
├── data/
│   └── en_climate_hourly_*.csv 11 monthly CSVs (May 2016–2026)
└── src/
    ├── data_loader.py          shared CSV loader (load_all, load_latest, FEATURE_ORDER)
    ├── producer.py             CSV -> raw-weather topic at 1 msg/sec
    ├── streams_app.py          Faust agent: raw-weather -> predictions
    └── consumer.py             predictions -> stdout
```
