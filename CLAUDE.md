# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Graduate coursework for **ENGR 5785G — Real-Time Data Analytics IoT** at Ontario Tech University. Two assignments:

- **Assignment 1:** End-to-end Kafka streaming pipeline with scikit-learn ML inference on real Environment Canada weather data.
- **Assignment 2:** SmartFactory IoT protocol integration — MQTT, CoAP, AMQP with packet-level analysis.

## Assignment 1 — Kafka + Faust ML Pipeline

### Setup

```powershell
cd assignment_1
uv python install 3.11    # Python 3.11 required; Faust breaks on 3.12+
uv venv --python 3.11
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt

docker compose up -d      # Starts Kafka + Zookeeper
docker compose ps         # Verify both services healthy
```

### Train the model

```powershell
jupyter nbconvert --to notebook --execute train_model.ipynb --output train_model.ipynb
# Produces model.joblib (LinearRegression, R²=0.966)
```

### Run (3 terminals, in this order)

```powershell
# Terminal 1 — streams processor (must start before producer to avoid missing messages)
faust -A src.streams_app worker -l info

# Terminal 2 — consumer (subscribes to predictions topic)
python -m src.consumer

# Terminal 3 — producer (replays latest month at 1 msg/sec)
python -m src.producer
```

### Architecture

```
CSV data (May 2016–2026)
    ↓
producer.py (confluent-kafka, 1 msg/sec) → [raw-weather topic]
    ↓
streams_app.py (Faust agent) → loads model.joblib → [predictions topic]
    ↓
consumer.py → formatted output: timestamp, current temp, predicted next-hour temp, delta direction
```

**Key source files:**
- [src/data_loader.py](assignment_1/src/data_loader.py) — shared CSV loader; defines `COL_MAP` and `FEATURE_ORDER`; distinguishes training (all 11 CSVs) vs. producer mode (latest only)
- [src/streams_app.py](assignment_1/src/streams_app.py) — Faust agent; loads `model.joblib` at startup; consumes `raw-weather`, publishes to `predictions`
- [src/producer.py](assignment_1/src/producer.py) — replays 479 test rows (May 2026) with JSON serialization
- [src/consumer.py](assignment_1/src/consumer.py) — prints delta direction (UP/DOWN), formatted with `rich` or plain stdout

## Assignment 2 — SmartFactory IoT Protocol Integration

### Setup

```bash
cd assignment_2
uv venv
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
uv pip install -r requirements.txt
bash setup.sh              # Starts Mosquitto + RabbitMQ via Docker
# Or start Docker services manually:
docker compose up -d       # Mosquitto + RabbitMQ + InfluxDB
```

### Run individual tasks

```bash
# Task 1 — MQTT
python -m src.mqtt.publisher &
python -m src.mqtt.subscriber

# Task 2 — CoAP
python -m src.coap.server &
python -m src.coap.observer

# Task 3 — AMQP (declare topology once, then producer + consumer)
python -m src.amqp.topology
python -m src.amqp.producer &
python -m src.amqp.consumer
```

### Tests

```bash
cd assignment_2
pytest tests/ -v
pytest tests/mqtt/test_publisher.py -v          # 8 assertions for Task 1
pytest tests/mqtt/test_qos_loss.py -v -s        # QoS 0/1/2 comparison table (100 msgs × 3 QoS)
pytest tests/amqp/test_topology.py -v
```

Tests use `unittest.mock.patch` — no running brokers required.

### Architecture

**SmartFactory:** 2 production lines × 3 sensors (temperature, vibration, power) with Gaussian noise simulation.

| Task | Protocol | Pattern | Key Feature |
|------|----------|---------|-------------|
| 1 | MQTT (paho) | Pub/Sub | QoS 0/1/2 per sensor type; LWT for line status; `clean_session=False` |
| 2 | CoAP (aiocoap) | Observe + Block2 | Observable sensors; 3 KB firmware manifest via Block2; stale sequence detection |
| 3 | AMQP (pika) | Topic Exchange + DLX | Publisher Confirms; manual ACK; 10% NACK → dead-letter routing |
| 4 | Wireshark | Packet capture | `scripts/capture.sh` → pcap files in `captures/` |
| 5 | Analysis | Comparative report | `report/comparison_report.md` + `report/packet_analysis.md` |

**MQTT QoS by sensor:**
- Temperature → QoS 1 (at-least-once)
- Vibration → QoS 0 (fire-and-forget)
- Power → QoS 2 (exactly-once)

**AMQP topology:** Topic exchange (`factory.events`) + Direct exchange for critical alerts. Critical threshold is 85°C → routes to `factory.{line}.temperature.critical`. Dead-letter exchange receives NACKed and TTL-expired messages.

**CoAP resources:** `/factory/line{1,2}/{temperature,vibration,power}` (Observable) + `/factory/actuator/{line}` + `/factory/manifest` (Block2 transfer).

## Conventions

- All components run as `python -m src.<module>` (package-relative imports).
- Infrastructure is always Docker-managed; clients must wait for broker readiness.
- Assignment 2 is TODO-driven: tests define the requirements; implement to make tests pass.
- `model.joblib` is committed (pre-trained); re-run the notebook only if retraining.