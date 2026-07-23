#!/usr/bin/env python3
"""Local dev server for a Scaleway Serverless Function (Python runtime).

Runs your function/handler.py locally so you can curl it without deploying.
Translates incoming HTTP requests into the event shape Scaleway passes to
`handle(evt, ctx)`, and translates the dict it returns back into an HTTP
response. Stdlib only, no dependencies required.

Usage:
    ./local_server.py [--port 8080] [--handler function/handler.py]
"""

import argparse
import base64
import importlib.util
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import dotenv


def load_handler(handler_path: Path):
    # handler.py does `from http_event import ...`, so its own directory
    # needs to be importable, same as it would be once deployed.
    sys.path.insert(0, str(handler_path.parent))

    spec = importlib.util.spec_from_file_location("handler", handler_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handle


def build_event(req: BaseHTTPRequestHandler, body_bytes: bytes) -> dict:
    parts = urlsplit(req.path)
    headers = {k.lower(): v for k, v in req.headers.items()}

    try:
        body_text = body_bytes.decode("utf-8")
        is_b64 = False
    except UnicodeDecodeError:
        body_text = base64.b64encode(body_bytes).decode("ascii")
        is_b64 = True

    query = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parts.query).items()}

    return {
        "httpMethod": req.command,
        "method": req.command,
        "path": parts.path,
        "rawPath": parts.path,
        "queryStringParameters": query,
        "headers": headers,
        "body": body_text,
        "isBase64Encoded": is_b64,
    }


def make_request_handler(handle_fn):
    class RequestHandler(BaseHTTPRequestHandler):
        def _handle(self):
            length = int(self.headers.get("content-length", 0) or 0)
            body_bytes = self.rfile.read(length) if length else b""
            evt = build_event(self, body_bytes)

            try:
                result = handle_fn(evt, {}) or {}
            except Exception as exc:  # surface handler errors instead of hanging the client
                body = f"handler error: {exc}".encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                raise

            status = result.get("statusCode", 200)
            resp_headers = result.get("headers") or {}
            body = result.get("body") or ""
            if result.get("isBase64Encoded"):
                out_bytes = base64.b64decode(body)
            else:
                out_bytes = body.encode("utf-8")

            self.send_response(status)
            for k, v in resp_headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(out_bytes)))
            self.end_headers()
            self.wfile.write(out_bytes)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _handle

    return RequestHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--handler",
        default="function/handler.py",
        help="path to handler.py (default: function/handler.py)",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="path to .env file (default: .env)",
    )

    args = parser.parse_args()

    dotenv.load_dotenv(args.env_file)

    handler_path = Path(args.handler).resolve()
    if not handler_path.exists():
        sys.exit(f"handler not found: {handler_path}")

    handle_fn = load_handler(handler_path)
    server = HTTPServer(("127.0.0.1", args.port), make_request_handler(handle_fn))
    print(f"serving {handler_path} on http://127.0.0.1:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
