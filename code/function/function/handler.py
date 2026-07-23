"""Hello world handler for a Scaleway Serverless Function (Python runtime).

`http_event.py` (next to this file) gives you method/path/route/body parsing
that works across Scaleway's HTTP event shapes.
"""

from http_event import match_route, get_method


def handle(evt, ctx):
    method = get_method(evt)
    path = match_route(evt)

    match (method, path):
        case ("GET", "/"):
            return {"statusCode": 200, "body": "Hello, world!"}
        case _:
            return {"statusCode": 404, "body": f"{method} {path}"}
