"""
Module 1 Assignment — CoAP-HTTP Proxy Integration Test (Task 2.3)

Starts the CoAP server and the HTTP→CoAP proxy, then verifies that:
  1. A standard HTTP GET returns the same JSON structure as a direct CoAP GET.
  2. HTTP response headers correctly map CoAP options (RFC 8075).
"""

import asyncio
import json

import aiocoap
import pytest
import pytest_asyncio
from aiocoap import Code, Message
from aiohttp import web

pytestmark = pytest.mark.asyncio


# ── Shared event loop (module scope) ─────────────────────────────────────────

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def coap_server():
    """Start the CoAP sensor server for the duration of this test module."""
    try:
        from src.coap.server import build_server
        ctx = await build_server()
        yield ctx
        await ctx.shutdown()
    except NotImplementedError:
        pytest.skip("CoAP server not yet implemented")


@pytest_asyncio.fixture(scope="module")
async def proxy_runner(coap_server):
    """Start the HTTP→CoAP proxy on localhost:8080."""
    from src.coap.proxy import create_proxy_app

    app = await create_proxy_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8080)
    await site.start()
    yield runner
    await runner.cleanup()


@pytest_asyncio.fixture(scope="module")
async def http_session(proxy_runner):
    """Shared aiohttp client session."""
    import aiohttp
    session = aiohttp.ClientSession()
    yield session
    await session.close()


@pytest_asyncio.fixture(scope="module")
async def coap_client():
    """Shared aiocoap client context for direct CoAP requests."""
    ctx = await aiocoap.Context.create_client_context()
    yield ctx
    await ctx.shutdown()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCoAPHTTPProxy:

    async def test_http_get_returns_200(self, http_session, proxy_runner):
        """HTTP GET /factory/line1/temperature must return 200 OK."""
        async with http_session.get(
            "http://localhost:8080/factory/line1/temperature"
        ) as resp:
            assert resp.status == 200, f"Expected 200, got {resp.status}"

    async def test_http_response_is_valid_json(self, http_session, proxy_runner):
        """HTTP response body must be valid JSON with value and unit keys."""
        async with http_session.get(
            "http://localhost:8080/factory/line1/temperature"
        ) as resp:
            data = await resp.json(content_type=None)
            assert "value" in data, "Response must contain 'value'"
            assert "unit" in data, "Response must contain 'unit'"
            assert data["unit"] == "C", f"Expected unit 'C', got {data['unit']}"

    async def test_http_matches_coap_structure(self, http_session, coap_client, proxy_runner):
        """HTTP proxy response must have the same JSON schema as a direct CoAP GET."""
        # Direct CoAP GET
        coap_req = Message(
            code=Code.GET, uri="coap://[::1]/factory/line1/temperature"
        )
        coap_resp = await coap_client.request(coap_req).response
        coap_data = json.loads(coap_resp.payload)

        # HTTP GET via proxy
        async with http_session.get(
            "http://localhost:8080/factory/line1/temperature"
        ) as resp:
            http_data = await resp.json(content_type=None)

        # Verify same top-level keys and units (values may differ by ≤5s update)
        assert set(coap_data.keys()) == set(http_data.keys()), (
            f"Key mismatch: CoAP={set(coap_data.keys())} HTTP={set(http_data.keys())}"
        )
        assert coap_data["unit"] == http_data["unit"], "Unit field must match"

    async def test_content_type_header_maps_from_coap_content_format(
        self, http_session, proxy_runner
    ):
        """HTTP Content-Type must reflect CoAP Content-Format option 50 (application/json)."""
        async with http_session.get(
            "http://localhost:8080/factory/line1/temperature"
        ) as resp:
            ct = resp.headers.get("Content-Type", "")
            assert "application/json" in ct, (
                f"Expected Content-Type: application/json, got {ct!r}\n"
                "CoAP Content-Format 50 → HTTP Content-Type: application/json"
            )

    async def test_cache_control_header_maps_from_coap_max_age(
        self, http_session, proxy_runner
    ):
        """HTTP Cache-Control: max-age must be present (maps from CoAP Max-Age option)."""
        async with http_session.get(
            "http://localhost:8080/factory/line1/temperature"
        ) as resp:
            cc = resp.headers.get("Cache-Control", "")
            assert "max-age" in cc, (
                f"Expected Cache-Control: max-age=N, got {cc!r}\n"
                "CoAP Max-Age option → HTTP Cache-Control: max-age"
            )

    async def test_proxy_vibration_resource(self, http_session, proxy_runner):
        """HTTP GET /factory/line1/vibration must return unit mm/s."""
        async with http_session.get(
            "http://localhost:8080/factory/line1/vibration"
        ) as resp:
            assert resp.status == 200
            data = await resp.json(content_type=None)
            assert data["unit"] == "mm/s"

    async def test_proxy_power_resource(self, http_session, proxy_runner):
        """HTTP GET /factory/line1/power must return unit kW."""
        async with http_session.get(
            "http://localhost:8080/factory/line1/power"
        ) as resp:
            assert resp.status == 200
            data = await resp.json(content_type=None)
            assert data["unit"] == "kW"
