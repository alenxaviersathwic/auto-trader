"""The HTTP logging middleware must never buffer a server-sent-events stream (the session loop and notifications
streams never end, so buffering them meant the browser sat on "connecting" forever)."""
import asyncio

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.core.logging.http_logger import HttpTrafficLoggingMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(HttpTrafficLoggingMiddleware)

    async def events():
        yield "event: loop\ndata: {}\n\n"
        await asyncio.sleep(3600)  # an open stream: never finishes

    @app.get("/api/v1/sessions/1/stream")
    async def stream():
        return StreamingResponse(events(), media_type="text/event-stream")

    return app


async def _first_body(app: FastAPI, path: str) -> bytes:
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
             "path": path, "raw_path": path.encode(), "query_string": b"", "headers": [], "client": ("t", 1),
             "server": ("t", 80), "root_path": ""}
    got: asyncio.Queue = asyncio.Queue()
    disconnect = asyncio.Event()

    sent_request = False

    async def receive():
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(msg):
        await got.put(msg)

    task = asyncio.create_task(app(scope, receive, send))
    try:
        while True:
            msg = await asyncio.wait_for(got.get(), timeout=1.0)
            if msg["type"] == "http.response.body" and msg.get("body"):
                return msg["body"]
    finally:
        disconnect.set()
        task.cancel()


def test_sse_passes_through_the_logging_middleware():
    body = asyncio.run(_first_body(_app(), "/api/v1/sessions/1/stream"))
    assert body.startswith(b"event: loop")
