"""
Task 2.3 — CoAP-HTTP Proxy

Starts an HTTP server on port 8080 that translates incoming HTTP GET
requests into CoAP GET requests (forwarded to our CoAP server on ::1:5683)
and returns the CoAP response as an HTTP response with properly mapped headers.

This implements the cross-protocol mapping described in RFC 8075.

Run with:
    python -m src.coap.proxy

Then in another terminal:
    curl http://localhost:8080/factory/line1/temperature
"""

import asyncio
import logging

import aiocoap
from aiocoap import Message, Code
from aiohttp import web

log = logging.getLogger(__name__)

COAP_SERVER_BASE = "coap://[::1]"
HTTP_HOST = "localhost"
HTTP_PORT = 8080

# CoAP Content-Format → HTTP Content-Type
_CONTENT_TYPE_MAP = {
    50:  "application/json",
    0:   "text/plain; charset=utf-8",
    40:  "application/link-format",
    60:  "application/cbor",
}


def _coap_code_to_http_status(coap_code) -> int:
    """Map CoAP response codes to HTTP status codes (RFC 8075 §5)."""
    dotted = coap_code.dotted
    if dotted == "2.05":
        return 200
    if dotted == "2.04":
        return 204
    if dotted == "4.00":
        return 400
    if dotted == "4.04":
        return 404
    if dotted == "4.05":
        return 405
    if dotted.startswith("2."):
        return 200
    if dotted.startswith("4."):
        return 400
    if dotted.startswith("5."):
        return 500
    return 200


async def _coap_get(ctx: aiocoap.Context, path: str) -> web.Response:
    """Forward an HTTP GET as a CoAP GET and translate the response."""
    uri = f"{COAP_SERVER_BASE}/{path}"
    log.debug("CoAP GET %s", uri)

    coap_req = Message(code=Code.GET, uri=uri)
    try:
        coap_resp = await ctx.request(coap_req).response
    except Exception as exc:
        log.error("CoAP request failed: %s", exc)
        return web.Response(status=502, text=f"CoAP upstream error: {exc}")

    # ── Header mapping (RFC 8075) ─────────────────────────────────────────
    content_format = coap_resp.opt.content_format
    content_type = _CONTENT_TYPE_MAP.get(content_format, "application/octet-stream")

    headers = {
        "X-CoAP-Response-Code": str(coap_resp.code),
    }

    # Max-Age option → Cache-Control: max-age
    max_age = coap_resp.opt.max_age
    if max_age is not None:
        headers["Cache-Control"] = f"max-age={max_age}"
    else:
        headers["Cache-Control"] = "max-age=60"

    # ETag option → ETag header
    if coap_resp.opt.etag is not None:
        headers["ETag"] = coap_resp.opt.etag.hex()

    http_status = _coap_code_to_http_status(coap_resp.code)

    return web.Response(
        status=http_status,
        body=coap_resp.payload,
        content_type=content_type,
        headers=headers,
    )


async def handle_request(request: web.Request) -> web.Response:
    """Route any HTTP GET to the CoAP backend."""
    path = request.match_info.get("path", "")
    ctx: aiocoap.Context = request.app["coap_ctx"]
    return await _coap_get(ctx, path)


async def create_proxy_app() -> web.Application:
    """Build and return the aiohttp application with a shared CoAP context."""
    app = web.Application()

    async def startup(app: web.Application) -> None:
        app["coap_ctx"] = await aiocoap.Context.create_client_context()
        log.info("CoAP client context ready")

    async def shutdown(app: web.Application) -> None:
        await app["coap_ctx"].shutdown()
        log.info("CoAP client context shut down")

    app.on_startup.append(startup)
    app.on_shutdown.append(shutdown)
    app.router.add_get("/{path:.*}", handle_request)
    return app


async def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)-8s  %(message)s")
    app = await create_proxy_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)
    await site.start()
    log.info("HTTP→CoAP proxy listening on http://%s:%d", HTTP_HOST, HTTP_PORT)
    log.info("Example: curl http://%s:%d/factory/line1/temperature", HTTP_HOST, HTTP_PORT)
    await asyncio.get_event_loop().create_future()  # run forever


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
