# Module 2 Assignment — SmartFactory IoT Protocol Integration

Repository for Ontario Tech course **202605 — Real-Time Data Analytics IoT**.

Student: Vitor Brandao Raposo

Student ID: 101011969

---

## Quick Start (Windows)

```powershell
# 1. Start Docker services (Mosquitto + RabbitMQ + InfluxDB)
docker compose up -d

# 2. Activate the project virtual environment
..\\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Confirm baseline tests pass
pytest tests/ -v --tb=short
# Expected: 29 passed, 8 skipped (AMQP topology not implemented)
```

---

## Repository Structure

```text
assignment_2/
├── src/
│   ├── mqtt/
│   │   ├── publisher.py      ← Task 1.1  Complete
│   │   └── subscriber.py     ← Task 1.2  Complete
│   ├── coap/
│   │   ├── server.py         ← Task 2.1  Complete
│   │   ├── observer.py       ← Task 2.2  Complete
│   │   └── proxy.py          ← Task 2.3  Complete
│   └── amqp/
│       ├── topology.py       ← Task 3.1  TODO (not in scope)
│       ├── producer.py       ← Task 3.2  TODO (not in scope)
│       └── consumer.py       ← Task 3.3  TODO (not in scope)
│
├── tests/
│   ├── mqtt/
│   │   ├── test_publisher.py    ← Do not modify
│   │   └── test_qos_loss.py     ← Do not modify (run with -s for table output)
│   ├── coap/
│   │   ├── test_server.py       ← Do not modify
│   │   └── test_proxy.py        ← Do not modify
│   └── amqp/
│       └── test_topology.py     ← Do not modify (skipped until Task 3 is done)
│
├── report/
│   ├── packet_analysis.md    ← Task 4  Annotation tables
│   └── comparison_report.md  ← Task 5  Protocol comparison
│
├── captures/                 ← Task 4  .pcap files (git-ignored)
├── scripts/
│   ├── capture.sh            ← Linux/macOS only
│   └── capture_win.py        ← Windows packet capture (use this on Windows)
├── config/
│   └── mosquitto.conf
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── setup.sh
```

---

## Task 1 — MQTT Sensor Publisher & Subscriber

Run in two separate terminals (virtual environment must be active in each):

```powershell
# Terminal 1 — Publisher
python -m src.mqtt.publisher

# Terminal 2 — Subscriber
python -m src.mqtt.subscriber
```

The publisher sends readings for 6 sensors (temperature / vibration / power × line1 / line2)
at 1-second intervals. The subscriber prints each message and fires CRITICAL ALERTs when
temperature exceeds 85 °C.

---

## Task 2 — CoAP Sensor Resource & Observer

```powershell
# Terminal 1 — CoAP server (must start first)
python -m src.coap.server

# Terminal 2 — Observer client (subscribes to both temperature resources)
python -m src.coap.observer

# Terminal 3 (optional) — CoAP→HTTP proxy for Task 2.3
python -m src.coap.proxy
```

> **Note:** Stop `src.coap.server` and `src.coap.proxy` before running `pytest tests/coap/`.
> The test fixtures start their own server/proxy on the same ports (5683, 8080) and will
> fail with "address already in use" if a live process is still running.

---

## Task 4 — Packet Capture

> **Administrator privileges required.**
> The Windows loopback adapter (NPF_Loopback) can only be captured with an elevated process.
> Open a **new PowerShell window as Administrator** for the capture step below.

1. Start the MQTT publisher and CoAP server in normal terminals (Tasks 1 + 2 above).
2. In the **Administrator** PowerShell:

```powershell
cd "C:\Users\Fox\Desktop\Thesis\Real_Time_Data_Analytics_IoT\assignment_2"
python scripts/capture_win.py
```

The script auto-detects the loopback interface and runs a 30-second capture, writing:

- `captures/mqtt.pcap` — MQTT traffic on port 1883
- `captures/coap.pcap` — CoAP traffic on UDP port 5683

**Alternative (no admin needed):** Open **Wireshark**, double-click
_Adapter for loopback traffic capture_, let it run for ~30 seconds, then export:

- Filter `tcp.port == 1883` → File → Export Specified Packets → `captures/mqtt.pcap`
- Filter `udp.port == 5683` → File → Export Specified Packets → `captures/coap.pcap`

---

## Task 5 — Protocol Analysis Reports

Fill in the two report files:

| File                          | Content                                                          |
| ----------------------------- | ---------------------------------------------------------------- |
| `report/packet_analysis.md`   | Wire-level annotations for MQTT and CoAP packets (Task 4 tables) |
| `report/comparison_report.md` | Protocol comparison essay — 1500–2000 words total                |

---

## Running Tests

Unit tests use `unittest.mock.patch` — no running broker or server required.

```powershell
# All tests
pytest tests/ -v --tb=short

# Individual task suites
pytest tests/mqtt/ -v --tb=short        # Task 1  (11 tests)
pytest tests/coap/test_server.py -v     # Task 2.1 (10 tests)
pytest tests/coap/test_proxy.py -v      # Task 2.3 (7 tests)

# QoS comparison experiment output (Task 1.3) — requires Mosquitto running
pytest tests/mqtt/test_qos_loss.py -v -s
```

**Expected result (Tasks 1 + 2 complete, Task 3 not implemented):**

```text
29 passed, 8 skipped
```

The 8 skipped are AMQP topology tests — they skip automatically until `src/amqp/topology.py` is implemented.

---

## Infrastructure

| Service                | Port  | Notes                                         |
| ---------------------- | ----- | --------------------------------------------- |
| Mosquitto MQTT         | 1883  | Started by `docker compose up -d`             |
| RabbitMQ AMQP          | 5672  | Started by `docker compose up -d`             |
| RabbitMQ Management UI | 15672 | <http://localhost:15672> (guest / guest)      |
| CoAP server (Python)   | 5683  | Started manually: `python -m src.coap.server` |
| CoAP→HTTP proxy        | 8080  | Started manually: `python -m src.coap.proxy`  |

```powershell
# Start all Docker services
docker compose up -d

# Stop all Docker services
docker compose down

# View logs
docker compose logs -f mosquitto
docker compose logs -f rabbitmq
```
