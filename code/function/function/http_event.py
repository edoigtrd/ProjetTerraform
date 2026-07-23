"""Generic helpers for parsing Scaleway Serverless Functions HTTP events.

Scaleway's Python function runtime hands `handle(event, context)` a dict whose
shape varies depending on the trigger (HTTP API gateway vs raw proxy). These
helpers normalize access to method, path, route and body regardless of which
shape shows up, so app-specific handler code doesn't need to know about it.

Drop this file next to handler.py and import what you need:

    from http_event import parse_body, match_route, get_method
"""

import base64
import json
from urllib.parse import parse_qs


def get_body_bytes(event: dict) -> bytes:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body)
    return body.encode("utf-8")


def get_content_type(headers: dict) -> str:
    headers = headers or {}
    ct = headers.get("content-type") or headers.get("Content-Type") or ""
    return ct.split(";")[0].strip().lower()


def parse_body(event: dict) -> dict:
    headers = event.get("headers") or {}
    content_type = get_content_type(headers)
    body_bytes = get_body_bytes(event)

    if content_type == "application/json":
        if not body_bytes:
            return {}
        return json.loads(body_bytes.decode("utf-8"))

    if content_type == "application/x-www-form-urlencoded":
        data = parse_qs(body_bytes.decode("utf-8"), keep_blank_values=True)
        return {k: (v[0] if len(v) == 1 else v) for k, v in data.items()}

    return {"raw": body_bytes.decode("utf-8", errors="replace")}


def get_method(evt: dict) -> str:
    return (
        evt.get("method")
        or evt.get("httpMethod")
        or (evt.get("requestContext") or {}).get("http", {}).get("method")
        or ""
    ).upper()


def get_path(evt: dict) -> str:
    # Common places depending on gateway / proxy integration
    return (
        evt.get("rawPath")
        or evt.get("path")
        or (evt.get("requestContext") or {}).get("http", {}).get("path")
        or (evt.get("requestContext") or {}).get("path")
        or ""
    )


def get_route_key(evt: dict) -> str:
    # HTTP API sometimes provides a "routeKey" like "GET /daily.jsonl"
    return evt.get("routeKey") or (evt.get("requestContext") or {}).get("routeKey") or ""


def get_query_params(evt: dict) -> dict:
    params = evt.get("queryStringParameters")
    if params:
        return dict(params)

    query_string = evt.get("rawQueryString")
    if not query_string:
        path = evt.get("rawPath") or evt.get("path") or ""
        if "?" in path:
            query_string = path.split("?", 1)[1]

    if not query_string:
        return {}

    parsed = parse_qs(query_string, keep_blank_values=True)
    return {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}


def match_route(evt: dict) -> str:
    route_key = get_route_key(evt)
    if route_key:
        # route_key can be "GET /daily.jsonl"
        parts = route_key.split(" ", 1)
        if len(parts) == 2:
            return parts[1]

    path = get_path(evt)
    return path.split("?", 1)[0]  # safety if query sneaks in
