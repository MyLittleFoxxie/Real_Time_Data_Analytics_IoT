"""
Module 1 Assignment — Task 2.1
CoAP Sensor Resource Server

Complete all TODO sections. The resource classes must match the
URIs and behaviours listed in the assignment spec.

Run with:  python -m src.coap.server
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timezone

import aiocoap
import aiocoap.resource as resource
from aiocoap import Code, Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

# ── Sensor simulation helpers ─────────────────────────────────────────────────

SENSOR_CONFIG = {
    "temperature": {"unit": "C",    "base": 70.0, "noise": 3.0},
    "vibration":   {"unit": "mm/s", "base": 1.2,  "noise": 0.3},
    "power":       {"unit": "kW",   "base": 45.0, "noise": 5.0},
}

def _sim(sensor: str) -> dict:
    cfg = SENSOR_CONFIG[sensor]
    return {
        "value": round(cfg["base"] + random.gauss(0, cfg["noise"]), 3),
        "unit":  cfg["unit"],
        "ts":    datetime.now(timezone.utc).isoformat(),
    }

def _json(data: dict) -> bytes:
    return json.dumps(data).encode()


# ── Observable Sensor Resource ────────────────────────────────────────────────

class SensorResource(resource.ObservableResource):
    """
    An observable CoAP resource that represents a single sensor on a line.

    TODO 1: Implement this class.
    Requirements:
      - Accept line and sensor_type in __init__
      - Store the current reading (initially simulated)
      - Start an asyncio background task (_update_loop) that:
          * Simulates a new reading every 5 seconds
          * Calls self.updated_state() to notify observers
      - Implement render_get:
          * Return a 2.05 Content response
          * Content-Format: 50 (application/json)
          * Payload: JSON-encoded current reading
    """

    def __init__(self, line: str, sensor_type: str):
        super().__init__()
        self.line        = line
        self.sensor_type = sensor_type
        self._reading    = _sim(sensor_type)
        self._task       = asyncio.ensure_future(self._update_loop())

    async def _update_loop(self) -> None:
        """
        TODO 2: Every 5 seconds, simulate a new reading and notify observers.
        """
        try:
            while True:
                await asyncio.sleep(5)
                self._reading = _sim(self.sensor_type)
                self.updated_state()
        except asyncio.CancelledError:
            pass

    async def render_get(self, request: Message) -> Message:
        """
        TODO 3: Return the current sensor reading as a JSON response.
        Hint: use aiocoap.numbers.contentformat.ContentFormat.JSON (value 50)
              or pass content_format=50 to Message(...)
        """
        return Message(code=Code.CONTENT, payload=_json(self._reading), content_format=50)


# ── Actuator Resource ─────────────────────────────────────────────────────────

class ActuatorResource(resource.Resource):
    """
    A CoAP resource representing a controllable fan actuator.

    TODO 4: Implement this class.
    Requirements:
      - Track state: "OFF" initially
      - render_get: return current state as JSON {"state": "ON"|"OFF"}
      - render_put: accept {"state": "ON"} or {"state": "OFF"}
          * Update internal state
          * Return 2.04 Changed on success
          * Return 4.00 Bad Request if payload is malformed or state is invalid
    """

    def __init__(self):
        super().__init__()
        self._state = "OFF"

    async def render_get(self, request: Message) -> Message:
        """TODO 5: Return current fan state as JSON."""
        return Message(code=Code.CONTENT, payload=_json({"state": self._state}), content_format=50)

    async def render_put(self, request: Message) -> Message:
        """TODO 6: Accept ON/OFF command and update state."""
        try:
            data = json.loads(request.payload)
            state = data.get("state")
            if state not in ("ON", "OFF"):
                return Message(code=Code.BAD_REQUEST, payload=b"state must be ON or OFF")
            self._state = state
            return Message(code=Code.CHANGED)
        except Exception:
            return Message(code=Code.BAD_REQUEST, payload=b"malformed JSON")


# ── Block-wise Manifest Resource ──────────────────────────────────────────────

class ManifestResource(resource.Resource):
    """
    A large resource that triggers CoAP Block2 transfer.

    TODO 7: Implement this class.
    Requirements:
      - render_get must return a payload of AT LEAST 3072 bytes (3 KB)
      - Content-Format: 50 (application/json)
      - The payload should be a realistic-looking firmware manifest
        (list of sensor firmware versions, checksums, update URLs, etc.)
      - aiocoap handles Block2 fragmentation automatically if the payload
        exceeds the negotiated block size — you just need to return the full payload
    """

    async def render_get(self, request: Message) -> Message:
        """TODO 8: Return a >= 3 KB JSON firmware manifest."""
        entries = [
            {
                "id": f"fw-sensor-{i:03d}",
                "component": ["temperature-sensor", "vibration-sensor", "power-meter"][i % 3],
                "version": f"{1 + i // 10}.{i % 10}.{i % 3}",
                "checksum": f"sha256:{i:064x}",
                "url": f"https://updates.smartfactory.io/firmware/fw-sensor-{i:03d}.bin",
                "size_bytes": 65536 + i * 128,
                "release_date": f"2026-0{1 + i % 9:01d}-{1 + i % 28:02d}",
                "target_devices": [f"line{1 + i % 2}/sensor-{i:03d}"],
                "min_hardware_rev": "B",
                "changelog": f"Bug fixes and stability improvements for sensor firmware version {i}.",
            }
            for i in range(55)
        ]
        manifest = {"schema_version": "2.1", "generated": "2026-05-28T00:00:00Z", "entries": entries}
        payload = json.dumps(manifest).encode()
        return Message(code=Code.CONTENT, payload=payload, content_format=50)


# ── Resource Tree & Server Setup ──────────────────────────────────────────────

async def build_server() -> aiocoap.Context:
    """
    TODO 9: Build the CoAP resource tree and create the server context.

    Register resources at these paths (use colon-separated path segments):
      factory/line1/temperature  → SensorResource("line1", "temperature")
      factory/line1/vibration    → SensorResource("line1", "vibration")
      factory/line1/power        → SensorResource("line1", "power")
      factory/line2/temperature  → SensorResource("line2", "temperature")
      actuator/line1/fan         → ActuatorResource()
      factory/manifest           → ManifestResource()

    Also add a /.well-known/core resource listing using resource.WKCResource.

    Return the created aiocoap.Context.
    """
    root = resource.Site()

    sensors = [
        SensorResource('line1', 'temperature'),
        SensorResource('line1', 'vibration'),
        SensorResource('line1', 'power'),
        SensorResource('line2', 'temperature'),
    ]
    root.add_resource(['factory', 'line1', 'temperature'], sensors[0])
    root.add_resource(['factory', 'line1', 'vibration'],   sensors[1])
    root.add_resource(['factory', 'line1', 'power'],       sensors[2])
    root.add_resource(['factory', 'line2', 'temperature'], sensors[3])
    root.add_resource(['actuator', 'line1', 'fan'],        ActuatorResource())
    root.add_resource(['factory', 'manifest'],             ManifestResource())
    root.add_resource(['.well-known', 'core'], resource.WKCResource(root.get_resources_as_linkheader))

    context = await aiocoap.Context.create_server_context(root, bind=("::1", 5683))

    _orig_shutdown = context.shutdown
    async def _shutdown():
        for s in sensors:
            s._task.cancel()
        await asyncio.gather(*[s._task for s in sensors], return_exceptions=True)
        await _orig_shutdown()
    context.shutdown = _shutdown

    return context


async def main() -> None:
    context = await build_server()
    log.info("CoAP server running on coap://localhost:5683")
    log.info("Resources: /factory/line{1,2}/{temperature,vibration,power}, /actuator/line1/fan, /factory/manifest")
    await asyncio.get_event_loop().create_future()  # run forever


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
