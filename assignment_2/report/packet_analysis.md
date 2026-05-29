# Module 1 Assignment — Packet Analysis
## Task 4: Wire-Level Protocol Annotation

Captures produced by `python scripts/capture_win.py` while
`python -m src.mqtt.publisher` and `python -m src.coap.server` were running.

---

## 4.2 MQTT Packet Annotations

### CONNECT Packet

Our publisher (`smartfactory-publisher-001`) connects with a persistent session,
60-second keep-alive, and a Last Will and Testament for `factory/line1/status`.

| Field | Offset (bytes) | Raw Hex | Decoded Value |
|-------|---------------|---------|---------------|
| Frame type + flags (byte 1) | 0 | `10` | Type=CONNECT (0001), flags=0000 |
| Remaining length (byte 2) | 1 | `6A` | 106 bytes |
| Protocol name length | 2–3 | `00 04` | 4 |
| Protocol name | 4–7 | `4D 51 54 54` | "MQTT" |
| Protocol version | 8 | `04` | 4 (MQTT 3.1.1) |
| Connect flags | 9 | `2C` | See breakdown below |
| Keep-alive | 10–11 | `00 3C` | 60 seconds |
| Client ID length | 12–13 | `00 1A` | 26 |
| Client ID | 14–39 | `73 6D 61 72 74 ...` | "smartfactory-publisher-001" |

**Connect Flags byte breakdown (`0x2C` = `0010 1100`):**

| Bit | Name | Value | Meaning |
|-----|------|-------|---------|
| 7 | Username flag | 0 | No username |
| 6 | Password flag | 0 | No password |
| 5 | Will retain | 1 | LWT message is retained |
| 4–3 | Will QoS | 01 | LWT at QoS 1 |
| 2 | Will flag | 1 | LWT is configured |
| 1 | Clean session | 0 | Persistent session (durable subscriptions) |
| 0 | Reserved | 0 | — |

---

### QoS 1 PUBLISH Packet

Topic: `factory/line1/temperature` (25 bytes). Payload: JSON sensor reading.

| Field | Offset (bytes) | Raw Hex | Decoded Value |
|-------|---------------|---------|---------------|
| Fixed header byte 1 | 0 | `32` | Type=PUBLISH(0011), DUP=0, QoS=01, RETAIN=0 |
| Remaining length | 1 | `7E` | 126 bytes |
| Topic length | 2–3 | `00 19` | 25 |
| Topic string | 4–28 | `66 61 63 74 6F 72 79 ...` | "factory/line1/temperature" |
| Packet Identifier | 29–30 | `00 01` | 1 |
| Payload | 31–… | `7B 22 6C 69 ...` | `{"line":"line1","sensor":"temperature","value":70.123,...}` |

**Fixed header byte 1 bit expansion (`0x32` = `0011 0010`):**

| Bits 7–4 (packet type) | Bit 3 (DUP) | Bits 2–1 (QoS) | Bit 0 (RETAIN) |
|------------------------|-------------|----------------|----------------|
| `0011` = PUBLISH (3) | `0` = not duplicate | `01` = QoS 1 | `0` = not retained |

---

### PUBACK Packet

| Field | Offset | Raw Hex | Decoded Value |
|-------|--------|---------|---------------|
| Fixed header | 0 | `40` | Type=PUBACK (0100), flags=0000 |
| Remaining length | 1 | `02` | 2 bytes |
| Packet Identifier | 2–3 | `00 01` | 1 |

**Packet Identifier match:** PUBLISH PKT ID = 1 ; PUBACK PKT ID = 1 ; **Match? YES ✓**

---

## 4.3 CoAP Packet Annotations

### CON GET Request

aiocoap sends a Confirmable GET to `coap://localhost/factory/line1/temperature`.
The Uri-Path is split into three option segments using delta encoding.

```
Bytes: 41 01 XX XX  TT  B7 66 61 63 74 6F 72 79  04 6C 69 6E 65 31  0B 74 65 6D 70 ...
       [  Header  ] [T] [delta=11,len=7,"factory"] [delta=0,len=4,"line1"] [delta=0,len=11,"temperature"]
```

| Field | Bits/Bytes | Raw Value | Decoded Value |
|-------|-----------|-----------|---------------|
| Version (bits 7–6) | 2 bits | `01` | 1 (always 1) |
| Type (bits 5–4) | 2 bits | `00` | 0 = CON (Confirmable) |
| TKL (bits 3–0) | 4 bits | `0001` | Token length = 1 |
| Code (byte 1) | 8 bits | `01` | 0.01 = GET |
| Message ID (bytes 2–3) | 16 bits | `XX XX` | Random per-request ID |
| Token (byte 4) | 1 byte | `TT` | 1-byte token value |
| Option 1 delta/len | 4+4 bits | `B7` | Delta=11 (Uri-Path), Len=7 |
| Option 1 value | 7 bytes | `66 61 63 74 6F 72 79` | "factory" |
| Option 2 delta/len | 4+4 bits | `04` | Delta=0 (same option), Len=4 |
| Option 2 value | 4 bytes | `6C 69 6E 65 31` | "line1" |
| Option 3 delta/len | 4+4 bits | `0B` | Delta=0 (same option), Len=11 |
| Option 3 value | 11 bytes | `74 65 6D 70 65 72 61 74 75 72 65` | "temperature" |

**Byte 0 full expansion (`0x41` = `0100 0001`):**

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
|-------|-------|-------|-------|-------|-------|-------|-------|
| Ver | Ver | T | T | TKL | TKL | TKL | TKL |
| `0` | `1` | `0` | `0` | `0` | `0` | `0` | `1` |

Ver=01=1, T=00=CON, TKL=0001=1-byte token.

---

### ACK 2.05 Content Response

aiocoap server returns the current sensor reading as JSON with Content-Format 50.

| Field | Bytes | Raw Hex | Decoded Value |
|-------|-------|---------|---------------|
| Fixed header byte 0 | 0 | `61` | Ver=01, T=10 (ACK), TKL=1 |
| Code byte 1 | 1 | `45` | 2.05 = Content |
| Message ID | 2–3 | `XX XX` | Matches request MID ✓ |
| Token | 4 | `TT` | Matches request token ✓ |
| Option: Content-Format | 5–6 | `C1 32` | Option#=12 (delta=12), Len=1, Value=50=application/json |
| Payload Marker | 7 | `FF` | 0xFF |
| Payload | 8–… | `7B 22 76 ...` | `{"value": 70.123, "unit": "C", "ts": "..."}` |

---

### Observe Notification

After registering with Observe=0, the server pushes a notification every 5 seconds
as `_update_loop` calls `updated_state()`.

| Field | Value |
|-------|-------|
| Observe option number | 6 |
| Observe sequence value | Starts at 0, increments by 1 per notification |
| Message type | NON (Non-confirmable — aiocoap default for observe updates) |
| Response code | 2.05 Content |

The observer client checks `response.opt.observe` and compares it against the
last seen sequence number. A notification is considered stale when
`seq <= last` (accounting for 24-bit wrap-around at `0xFFFFFF`).

---

## 4.4 AMQP Frame Annotations

*Section not completed — AMQP (Task 3) was excluded from the implementation scope.*

---

*Module 1 Assignment — Real-Time Data Analytics for IoT*
