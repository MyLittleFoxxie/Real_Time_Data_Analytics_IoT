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

---

## Assignment 2 — SmartFactory IoT Protocol Integration

ENGR 5785G Assignment 2. Multi-protocol IoT backend for a simulated factory with
2 production lines × 3 sensors (temperature, vibration, power). Implements MQTT
pub/sub with QoS levels, CoAP observable resources with Block2 transfer, and an
HTTP→CoAP cross-protocol proxy. AMQP (Task 3) was excluded from scope.

All assignment files live in [assignment_2/](assignment_2/). The instructions below
assume you `cd assignment_2` before running anything.

### Stack

- **MQTT:** `paho-mqtt` — publisher with LWT + persistent session, wildcard subscriber
- **CoAP:** `aiocoap[all]` — observable sensor resources, Block2 manifest, actuator PUT
- **HTTP proxy:** `aiohttp` — HTTP→CoAP cross-protocol bridge (RFC 8075)
- **Broker:** Mosquitto via Docker Compose
- **Testing:** `pytest` + `pytest-asyncio`

### Factory Setup

| | Line 1 | Line 2 |
|---|---|---|
| Temperature (°C) | QoS 1 / Observable | QoS 1 / Observable |
| Vibration (mm/s) | QoS 0 / Observable | — |
| Power (kW) | QoS 2 | — |
| Cooling fan | PUT /actuator/line1/fan | — |

Critical alert threshold: temperature > 85 °C.

### Setup

```powershell
cd assignment_2
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
docker compose up -d mosquitto    # start MQTT broker
```

### Run individual tasks

```powershell
# Task 1 — MQTT (requires mosquitto running)
python -m src.mqtt.publisher      # Terminal 1
python -m src.mqtt.subscriber     # Terminal 2

# Task 2 — CoAP (no broker required)
python -m src.coap.server         # Terminal 1
python -m src.coap.observer       # Terminal 2

# Task 2.3 — CoAP-HTTP proxy (requires CoAP server running)
python -m src.coap.proxy          # serves http://localhost:8080
# curl http://localhost:8080/factory/line1/temperature
```

### Tests

```powershell
# MQTT publisher + subscriber (no broker required — uses mocks)
pytest tests/mqtt/test_publisher.py -v

# MQTT QoS comparison (requires Docker Mosquitto on localhost:1883)
pytest tests/mqtt/test_qos_loss.py -v -s

# CoAP server resources
pytest tests/coap/test_server.py -v

# CoAP-HTTP proxy integration
pytest tests/coap/test_proxy.py -v

# Full non-AMQP suite
pytest tests/mqtt/test_publisher.py tests/coap/ -v
```

All non-AMQP tests pass (28 tests): 11 MQTT unit tests, 10 CoAP server tests, 7 proxy tests.

### Windows-specific notes

aiocoap requires `SelectorEventLoop` on Windows (default is `ProactorEventLoop`).
The `conftest.py` at the project root sets this automatically alongside a compatibility
shim for `pytest-asyncio` 0.21.x + pytest 8.x. The CoAP server binds to `[::1]:5683`
because Windows resolves `localhost` to `::1` (IPv6) before `127.0.0.1`.

### Packet captures

With Wireshark installed (`winget install Wireshark.Wireshark`):

```powershell
# Start publisher + server first, then:
python scripts/capture_win.py     # captures mqtt.pcap + coap.pcap in captures/
```

### Architecture

```
[Sensors: line1/line2 × temperature/vibration/power]
              |
      MQTT (paho)          CoAP (aiocoap)
      publisher.py         server.py
          |                    |
     Mosquitto            aiocoap server
     broker                ::1:5683
          |                    |
    subscriber.py         observer.py   proxy.py
    (wildcard + alerts)   (Observe +    (HTTP:8080
                           Block2)       → CoAP)
```

### Repo layout

```
assignment_2/
├── docker-compose.yml          Mosquitto + RabbitMQ + InfluxDB
├── requirements.txt
├── conftest.py                 Windows event-loop + pytest-asyncio shims
├── pytest.ini
├── src/
│   ├── mqtt/
│   │   ├── publisher.py        Task 1.1 — 6-sensor MQTT publisher, LWT, QoS per type
│   │   └── subscriber.py       Task 1.2 — wildcard subscriber, critical alerts
│   ├── coap/
│   │   ├── server.py           Task 2.1 — observable resources, actuator, Block2 manifest
│   │   ├── observer.py         Task 2.2 — concurrent observe + stale detection + manifest fetch
│   │   └── proxy.py            Task 2.3 — HTTP→CoAP cross-protocol proxy (RFC 8075)
│   └── amqp/                   Task 3 (skipped)
├── tests/
│   ├── mqtt/
│   │   ├── test_publisher.py   11 unit tests (mocked broker)
│   │   └── test_qos_loss.py    QoS comparison — requires live Mosquitto
│   └── coap/
│       ├── test_server.py      10 integration tests (real aiocoap server)
│       └── test_proxy.py       7 integration tests (HTTP→CoAP proxy)
├── scripts/
│   ├── capture.sh              Linux/macOS tshark capture
│   └── capture_win.py          Windows tshark capture (auto-detects interface)
├── captures/                   .pcap output (git-ignored)
└── report/
    ├── packet_analysis.md      Task 4 — MQTT + CoAP wire-level annotations
    └── comparison_report.md    Task 5 — QoS table, proxy mapping, recommendations
```
