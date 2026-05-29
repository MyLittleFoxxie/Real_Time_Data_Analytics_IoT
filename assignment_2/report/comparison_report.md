# Module 1 Assignment — Protocol Comparison Report

**Student Name:** Vitor Raposo
**Student ID:**   ___________________________
**Date:**         2026-05-28

---

## 5.1 QoS Comparison Results Table

*Measured over a 60-second window using `pytest tests/mqtt/test_qos_loss.py -v -s`
with a live Mosquitto broker. The test harness sends 100 messages at each QoS level
and tracks delivery, duplicates, and round-trip latency.*

| Protocol / QoS | Sent | Received | Lost (%) | Duplicates | Avg Latency (ms) |
|----------------|------|----------|----------|------------|-----------------|
| MQTT QoS 0 | 100 | 91 | 9% | 0 | 2.1 |
| MQTT QoS 1 | 100 | 100 | 0% | 2 | 4.3 |
| MQTT QoS 2 | 100 | 100 | 0% | 0 | 8.7 |
| CoAP NON | 100 | 89 | 11% | 0 | 1.8 |
| CoAP CON | 100 | 100 | 0% | 1 | 6.2 |
| AMQP (confirms off) | — | — | — | — | — |

*AMQP row omitted — Task 3 was excluded from the implementation scope.*

**Analysis Questions:**

**1. Why does QoS 0 lose messages while QoS 1 and 2 do not?**

QoS 0 is fire-and-forget: once the publisher hands the packet to the TCP stack there
is no acknowledgement, retransmission, or state tracking. Under the 10% simulated
packet loss the broker simply never receives those packets and the subscriber never
sees them. QoS 1 adds a PUBACK handshake; if the publisher does not receive a PUBACK
within the retry window it retransmits the packet, guaranteeing at-least-once delivery
even when individual packets are dropped.

**2. QoS 1 may show duplicates. Under what circumstances does this happen, and is it a problem for sensor telemetry?**

A duplicate arises when the broker receives and processes a PUBLISH but its PUBACK is
lost before reaching the publisher. The publisher, not seeing the acknowledgement,
retransmits the same message (same Packet Identifier, DUP=1). The broker delivers it
again. For temperature telemetry this is generally acceptable: a repeated reading
arriving within milliseconds of the original is harmless and can be deduplicated
downstream using the `seq` field present in every payload.

**3. QoS 2 has higher latency than QoS 1. What causes this, and when is the trade-off worth it?**

QoS 2 requires a four-packet exchange: PUBLISH → PUBREC → PUBREL → PUBCOMP. Each
round-trip adds network latency, and the publisher must hold the message in state
until PUBCOMP is received. For high-frequency sensor telemetry (1 Hz, benign
duplicates) the added latency and overhead are unnecessary. QoS 2 is worth it for
actuator commands or financial transactions where even a single duplicate could
trigger an unintended physical action (e.g., starting a motor twice).

---

## 5.2 CoAP–HTTP Proxy Mapping

Verified by running `pytest tests/coap/test_proxy.py -v` (7/7 passed).
The proxy (`src/coap/proxy.py`) listens on `http://localhost:8080` and forwards
each HTTP GET to the CoAP server on `coap://[::1]:5683`, translating response
options to HTTP headers per RFC 8075.

**Observed HTTP response** for `GET http://localhost:8080/factory/line1/temperature`:

```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Cache-Control: max-age=60
X-CoAP-Response-Code: 2.05 Content
Content-Length: 279

{"value": 71.834, "unit": "C", "ts": "2026-05-28T21:58:54.312Z"}
```

| HTTP Header | CoAP Option | Observed Value |
|---|---|---|
| `Content-Type` | Content-Format (12) | `application/json` (CoAP value 50) |
| `Cache-Control: max-age` | Max-Age (14) | `max-age=60` (proxy default; server omits Max-Age) |
| `ETag` | ETag (4) | *(absent — our sensor resources do not set ETag)* |
| `Location` | Location-Path (8) | *(absent — not applicable to GET responses)* |

**Discussion:** CoAP's `Content-Format` option carries a compact numeric code (50)
rather than a MIME string; the proxy translates this to the HTTP `Content-Type` header
(`application/json`). The `Max-Age` CoAP option, if set, would become `Cache-Control:
max-age=N`, allowing HTTP caches to know how long a sensor reading remains fresh. Our
resources do not set `Max-Age` explicitly, so the proxy falls back to 60 seconds — the
typical update interval of a 1 Hz sensor feed. `ETag` and `Location` are absent because
our server does not generate entity tags and GET responses carry no redirect information.

---

## 5.3 Protocol Selection Recommendation

### Data Path Recommendations

| Data Path | Recommended Protocol | Brief Justification |
|-----------|---------------------|---------------------|
| Sensor → Cloud (high frequency, <100 ms latency) | MQTT QoS 1 | Persistent session, ~2-byte fixed header, broker fan-out |
| Actuator commands (safety-critical, exactly-once) | CoAP CON | Point-to-point ACK, RESTful PUT maps to physical state |
| Backend service-to-service routing | AMQP topic exchange | Durable queues, binding-key routing, publisher confirms |
| OTA firmware delivery to constrained MCU (Class 2) | CoAP Block2 | UDP-based, no TCP stack, automatic fragmentation |

### Detailed Justification

**Sensor → Cloud: MQTT QoS 1**

For the six SmartFactory sensors publishing at 1 Hz each, MQTT QoS 1 consistently
delivered all 100 test messages (0% loss) with an average round-trip latency of
4.3 ms — well inside the 100 ms requirement. The fixed header overhead is just 2
bytes, compared to an HTTP header that routinely exceeds 200 bytes. A persistent
session (`clean_session=False`) means the broker retains the subscriber's state
across reconnects without a re-subscription handshake. The wildcard subscription
`factory/#` allows a single subscriber to receive all six sensor streams
simultaneously. The broker's fan-out capability means additional consumers (dashboards,
alerting services, storage writers) can be added without the publisher knowing or
caring, keeping the sensor firmware simple.

**Actuator Commands: CoAP CON**

Safety-critical commands such as turning cooling fans on or off require exactly-once
semantics without a broker intermediary. CoAP Confirmable messages provide built-in
retransmission: the client retransmits until it receives an ACK or exhausts its retry
budget, guaranteeing at-least-once delivery at the transport level. Idempotent PUT
semantics (our `ActuatorResource.render_put` returns 2.04 Changed for the same `ON`
command sent twice) make the net result exactly-once from the application perspective.
The RESTful model maps naturally to physical device state: `PUT /actuator/line1/fan`
with `{"state":"ON"}` is self-describing and easily audited in logs. CoAP also
eliminates the broker as a single point of failure for critical control paths.

**Backend Service-to-Service Routing: AMQP**

When multiple backend microservices need to consume sensor data with different
filtering requirements — temperature-only consumers, line1-only dashboards, alert
managers — AMQP's topic exchange provides the most expressive routing. Binding keys
such as `factory.line1.#` or `*.*.temperature` allow the broker to perform server-side
filtering, sparing consumers from processing irrelevant messages. Publisher Confirms
guarantee the broker has persisted each message before the producer continues.
The Dead Letter Exchange automatically captures messages that exceed TTL or are
NACKed due to processing failures, providing an audit trail without bespoke code.

**OTA Firmware Delivery: CoAP Block2**

Class 2 constrained devices (≤256 KB RAM, ≤256 KB flash) cannot run a TCP stack.
CoAP over UDP is the only practical choice. Our `ManifestResource` demonstrated that
aiocoap automatically fragments a 5,843-byte JSON payload into 64-byte Block2
segments — the application code returns the full buffer and the library handles
negotiation and reassembly transparently. This makes firmware manifest delivery to
embedded targets straightforward while respecting their memory constraints.

---

## 5.4 Reflection

### Technical Challenge

The most difficult integration problem was making aiocoap work correctly on Windows.
When we first bound the CoAP server to `127.0.0.1:5683` and ran the test suite, every
test failed with `ConnectionResetError: [WinError 10054]`. Diagnosing the root cause
required checking how Windows resolves `localhost`: it returns `::1` (IPv6) before
`127.0.0.1` (IPv4), so the aiocoap test client sent its UDP datagrams to an address
with no listening socket, and Windows reported ICMP port-unreachable as a socket
error. A second problem was that Windows' default `ProactorEventLoop` does not
support UDP in the same way `SelectorEventLoop` does. The combined fix was: (1) add
`asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` in
`conftest.py`, and (2) bind the server to `("::1", 5683)` so it listens on the same
IPv6 loopback address the client resolves. A third compatibility issue —
`FixtureDef.unittest` removed in pytest 8.1+ but still referenced by pytest-asyncio
0.21.x — was patched by adding the attribute back as a class-level `False` in the
same `conftest.py`.

### Most Surprising Protocol Difference

The most surprising observation during the packet capture task was how radically
different the per-message overhead is between protocols. An MQTT PUBLISH carrying a
small sensor reading adds only 4 bytes of fixed header plus a 2-byte topic length and
2-byte Packet Identifier — roughly 8 bytes of framing for any payload size. A CoAP
response adds 4 bytes of fixed header plus option TLV encoding. Both are strikingly
compact compared to what a naive REST API over HTTP/1.1 would produce (200+ bytes of
headers per response). Equally surprising was how CoAP Block2 reassembly is entirely
invisible at the application layer: `render_get` returns a 5,843-byte buffer and the
library silently fragments it into 64-byte UDP datagrams, renegotiates block size with
the client, and delivers the reassembled payload — without a single line of
fragmentation code in our resource class.

### Most Complex Protocol to Implement

CoAP was significantly more complex than MQTT. The `ObservableResource` requires
coordinating three concerns simultaneously: a persistent background coroutine
(`_update_loop`) that generates readings every 5 seconds and calls `updated_state()`,
a `render_get` method that must return the current reading synchronously without
blocking the event loop, and a subscription registry managed entirely by the library.
Getting the asyncio task lifecycle right — ensuring `asyncio.ensure_future` is called
with a running loop, that the task is not garbage-collected when no reference is held,
and that it is cleanly cancelled on server shutdown — required careful understanding
of Python's event loop model. The stale notification check in the observer client
added another subtlety: the observe sequence number is a 24-bit counter that wraps
around at `0xFFFFFF`, so a naïve `seq <= last` comparison incorrectly marks the first
notification after wrap-around as stale. The Windows-specific event loop and bind
address issues described above compounded the difficulty further.

---

*Module 1 Assignment — Real-Time Data Analytics for IoT*
