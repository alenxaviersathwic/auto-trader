import json
import logging
import time
from typing import Any, Set
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging.flow_context import LogFlowContext
from app.core.logging.logger import (
    BOLD,
    BRIGHT_BLACK,
    BRIGHT_CYAN,
    BRIGHT_GREEN,
    BRIGHT_RED,
    BRIGHT_WHITE,
    BRIGHT_YELLOW,
    CYAN,
    DIM,
    GREEN,
    MAGENTA,
    RED,
    RESET,
    WHITE,
    YELLOW,
)

logger = logging.getLogger("http.traffic")

HIGH_FREQUENCY_POLLING_PREFIXES: Set[str] = {
    "/actuator",
    "/api/v1/health",
    "/health",
}

FLOW_ID_HEADER = "X-Flow-Id"

SENSITIVE_FIELDS = {
    "password",
    "pin",
    "totp",
    "totpsecret",
    "secret",
    "apisecret",
    "authorization",
    "token",
    "accesstoken",
    "cookie",
    "set-cookie",
    "x-api-key",
    "master_encryption_key",
    "masterencryptionkey",
}


def mask_sensitive_data(obj: Any) -> Any:
    """Recursively masks sensitive credentials in request/response payloads."""
    if isinstance(obj, dict):
        masked = {}
        for k, v in obj.items():
            if str(k).lower().replace("_", "").replace("-", "") in SENSITIVE_FIELDS:
                masked[k] = "******"
            else:
                masked[k] = mask_sensitive_data(v)
        return masked
    elif isinstance(obj, list):
        return [mask_sensitive_data(item) for item in obj]
    return obj


def format_headers(headers: dict) -> list[str]:
    """Formats HTTP headers with sensitive values masked."""
    lines = []
    for k, v in headers.items():
        k_lower = k.lower()
        if k_lower in SENSITIVE_FIELDS:
            lines.append(f"    {BRIGHT_BLACK}{k}:{RESET} ******")
        else:
            lines.append(f"    {BRIGHT_BLACK}{k}:{RESET} {v}")
    return lines


def is_polling_path(path: str) -> bool:
    if not path:
        return False
    for prefix in HIGH_FREQUENCY_POLLING_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class HttpTrafficLoggingMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive HTTP Traffic Logger with Flow ID correlation and daily file logging.
    Directly matches trading-engine's LogFlowFilter & RequestLoggingFilter flow.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Manage Flow ID correlation context
        incoming_flow_id = request.headers.get(FLOW_ID_HEADER)
        flow_id = LogFlowContext.start(incoming_flow_id)

        start_time = time.perf_counter()
        path = request.url.path
        method = request.method
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        query_str = f"?{request.url.query}" if request.url.query else ""
        full_uri = f"{path}{query_str}"

        is_polling = method == "GET" and is_polling_path(path)

        # 2. Standard Flow Log for incoming request
        if not is_polling:
            logger.info(
                f"INCOMING REQUEST | ClientIP: {client_host} | Method: {method} | URI: {full_uri}"
            )

        # Capture Request Body if not polling
        req_body_bytes = b""
        req_body_str = None
        if not is_polling:
            req_body_bytes = await request.body()
            if req_body_bytes:
                try:
                    parsed_json = json.loads(req_body_bytes.decode("utf-8"))
                    masked_json = mask_sensitive_data(parsed_json)
                    req_body_str = json.dumps(masked_json, indent=2)
                except Exception:
                    req_body_str = req_body_bytes.decode("utf-8", errors="replace")

        try:
            # Process Request
            response = await call_next(request)
        finally:
            pass

        duration_ms = (time.perf_counter() - start_time) * 1000
        status_code = response.status_code

        # Propagate flow ID in response headers
        response.headers[FLOW_ID_HEADER] = flow_id

        # 3. Standard Flow Log for outgoing response
        if not is_polling or status_code >= 400:
            if status_code >= 400:
                logger.warning(
                    f"OUTGOING RESPONSE | ClientIP: {client_host} | Method: {method} | URI: {full_uri} | Status: {status_code} | Duration: {duration_ms:.2f}ms"
                )
            else:
                logger.info(
                    f"OUTGOING RESPONSE | ClientIP: {client_host} | Method: {method} | URI: {full_uri} | Status: {status_code} | Duration: {duration_ms:.2f}ms"
                )

        # For polling endpoints, skip multi-line terminal inspect box
        if is_polling:
            LogFlowContext.clear()
            return response

        # 4. Rich Inspection Box in console for deep debugging
        # Capture Response Body
        res_body_bytes = b""
        async for chunk in response.body_iterator:
            res_body_bytes += chunk

        async def new_body_iterator():
            yield res_body_bytes

        response.body_iterator = new_body_iterator()

        res_body_str = None
        if res_body_bytes:
            try:
                parsed_res = json.loads(res_body_bytes.decode("utf-8"))
                masked_res = mask_sensitive_data(parsed_res)
                res_body_str = json.dumps(masked_res, indent=2)
            except Exception:
                res_body_str = res_body_bytes.decode("utf-8", errors="replace")

        method_color = {
            "GET": CYAN,
            "POST": GREEN,
            "PUT": YELLOW,
            "DELETE": RED,
        }.get(method, MAGENTA)

        if 200 <= status_code < 300:
            status_color = BRIGHT_GREEN
            status_text = "OK"
        elif 300 <= status_code < 400:
            status_color = BRIGHT_CYAN
            status_text = "REDIRECT"
        elif 400 <= status_code < 500:
            status_color = BRIGHT_YELLOW
            status_text = "CLIENT_ERR"
        else:
            status_color = BRIGHT_RED
            status_text = "SERVER_ERR"

        box_lines = []
        box_lines.append(f"{BRIGHT_BLACK}┌─── HTTP REQUEST [{flow_id}] ────────────────────────────────────────{RESET}")
        box_lines.append(f"{BRIGHT_BLACK}│{RESET} {method_color}{BOLD}{method}{RESET} {BRIGHT_WHITE}{full_uri}{RESET}")
        box_lines.append(f"{BRIGHT_BLACK}│{RESET} {DIM}Client:{RESET} {client_host}:{client_port}")

        box_lines.append(f"{BRIGHT_BLACK}│{RESET} {DIM}Headers:{RESET}")
        for h_line in format_headers(dict(request.headers)):
            box_lines.append(f"{BRIGHT_BLACK}│{RESET} {h_line}")

        if req_body_str:
            box_lines.append(f"{BRIGHT_BLACK}│{RESET} {DIM}Body:{RESET}")
            for b_line in req_body_str.splitlines():
                box_lines.append(f"{BRIGHT_BLACK}│{RESET}   {b_line}")

        box_lines.append(f"{BRIGHT_BLACK}├─── HTTP RESPONSE [{flow_id}] ───────────────────────────────────────{RESET}")
        box_lines.append(
            f"{BRIGHT_BLACK}│{RESET} {DIM}Status:{RESET} {status_color}{BOLD}{status_code} {status_text}{RESET} "
            f"{BRIGHT_BLACK}(latency: {duration_ms:.2f}ms){RESET}"
        )

        box_lines.append(f"{BRIGHT_BLACK}│{RESET} {DIM}Headers:{RESET}")
        for h_line in format_headers(dict(response.headers)):
            box_lines.append(f"{BRIGHT_BLACK}│{RESET} {h_line}")

        if res_body_str:
            box_lines.append(f"{BRIGHT_BLACK}│{RESET} {DIM}Body:{RESET}")
            for b_line in res_body_str.splitlines():
                box_lines.append(f"{BRIGHT_BLACK}│{RESET}   {b_line}")

        box_lines.append(f"{BRIGHT_BLACK}└─────────────────────────────────────────────────────────────────────────{RESET}")

        print("\n".join(box_lines), flush=True)

        LogFlowContext.clear()
        return response
