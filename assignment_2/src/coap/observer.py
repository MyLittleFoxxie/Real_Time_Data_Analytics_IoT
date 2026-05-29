"""
Module 1 Assignment — Task 2.2
CoAP Observer Client

Complete all TODO sections.

Run with:  python -m src.coap.observer
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import aiocoap
from aiocoap import Message, Code

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

SERVER_BASE = "coap://[::1]"
OBSERVE_DURATION = 60   # seconds before clean deregister


class FactoryObserver:
    """Observes CoAP sensor resources and reassembles Block2 transfers."""

    def __init__(self):
        self._ctx = None
        self._last_seq: dict[str, int] = {}     # uri -> last observe sequence number
        self._stale_count: dict[str, int] = {}  # uri -> stale notification count

    # ── Setup ──────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Create the aiocoap client context."""
        self._ctx = await aiocoap.Context.create_client_context()

    async def stop(self) -> None:
        """Clean up the context."""
        if self._ctx:
            await self._ctx.shutdown()

    # ── Observation ────────────────────────────────────────────────────────────

    async def observe_resource(self, uri: str) -> None:
        """
        TODO 1: Subscribe to a single observable CoAP resource.
        Requirements:
          - Build a GET request with observe=0 (register)
          - Use self._ctx.request(request_obj) to get a RequestObservation
          - Iterate over the observation using `async for response in pr.observation:`
          - For each notification, call _handle_notification(uri, response)
          - After OBSERVE_DURATION seconds, cancel the observation (pr.observation.cancel())
          - Log "Deregistered from {uri}" after cancellation
        Hint: wrap the observation loop in asyncio.wait_for or use asyncio.create_task
              to run both line1 and line2 observations concurrently.
        """
        request = Message(code=Code.GET, uri=uri, observe=0)
        pr = self._ctx.request(request)
        response = await pr.response
        self._handle_notification(uri, response)
        start = asyncio.get_event_loop().time()
        try:
            async for notification in pr.observation:
                self._handle_notification(uri, notification)
                if asyncio.get_event_loop().time() - start >= OBSERVE_DURATION:
                    break
        finally:
            pr.observation.cancel()
            log.info(f"Deregistered from {uri}")

    def _handle_notification(self, uri: str, response: Message) -> None:
        """
        TODO 2: Process a single Observe notification.
        Requirements:
          - Extract the Observe option sequence number from response.opt.observe
          - Check for stale notification:
              * If the sequence number <= last seen (accounting for wrap-around at 2^24):
                  - Increment self._stale_count[uri]
                  - Log "STALE notification on {uri}: seq={seq} <= last={last}"
                  - RETURN (do not process the stale value)
          - Update self._last_seq[uri]
          - Parse response.payload as JSON
          - Log:
              [OBSERVE] {uri}  seq={seq}  val={value} {unit}  @ {timestamp}
        """
        seq = response.opt.observe
        last = self._last_seq.get(uri, -1)
        if last >= 0 and seq is not None:
            wrap = last > 0xF00000 and seq < 0x100000
            if seq <= last and not wrap:
                self._stale_count[uri] = self._stale_count.get(uri, 0) + 1
                log.warning(f"STALE notification on {uri}: seq={seq} <= last={last}")
                return
        if seq is not None:
            self._last_seq[uri] = seq
        try:
            data = json.loads(response.payload)
            log.info(f"[OBSERVE] {uri}  seq={seq}  val={data.get('value')} {data.get('unit')}  @ {data.get('ts')}")
        except Exception:
            log.info(f"[OBSERVE] {uri}  seq={seq}  raw={response.payload}")

    # ── Block2 Transfer ────────────────────────────────────────────────────────

    async def fetch_manifest(self) -> None:
        """
        TODO 3: Perform a GET on /factory/manifest and reassemble Block2.
        Requirements:
          - aiocoap handles Block2 reassembly automatically — just await the response
          - Log: "Manifest received: {len(payload)} bytes"
          - Parse as JSON and count the number of top-level items
          - Log: "Firmware entries in manifest: {count}"
          - Log: "Block2 transfer complete"

        Bonus: manually track how many Block2 blocks were received by
               checking response.opt.block2 if available.
        """
        request = Message(code=Code.GET, uri=f"{SERVER_BASE}/factory/manifest")
        response = await self._ctx.request(request).response
        log.info(f"Manifest received: {len(response.payload)} bytes")
        data = json.loads(response.payload)
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict) and "entries" in data:
            count = len(data["entries"])
        else:
            count = len(data)
        log.info(f"Firmware entries in manifest: {count}")
        log.info("Block2 transfer complete")

    # ── Run ────────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        TODO 4: Run all observations concurrently, then fetch the manifest.
        Requirements:
          - Start observe_resource for both:
              coap://localhost/factory/line1/temperature
              coap://localhost/factory/line2/temperature
          - Run them concurrently using asyncio.gather
          - After both complete (OBSERVE_DURATION seconds), call fetch_manifest
          - Print a final summary: stale notification counts per URI
        """
        await self.start()
        try:
            await asyncio.gather(
                self.observe_resource(f"{SERVER_BASE}/factory/line1/temperature"),
                self.observe_resource(f"{SERVER_BASE}/factory/line2/temperature"),
            )
            await self.fetch_manifest()
            for uri, count in self._stale_count.items():
                log.info(f"Stale notifications for {uri}: {count}")
        finally:
            await self.stop()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    observer = FactoryObserver()
    asyncio.run(observer.run())
