"""Shared test helpers for constructing real SDK exception instances.

Both the anthropic and openai SDKs (Stainless-generated) require a genuine
httpx2 Response/Request to build their exception types, so tests build one
instead of guessing at a simpler constructor.
"""

from __future__ import annotations

import httpx2


def make_status_error(exc_cls, *, status_code: int, message: str, error_type: str):
    request = httpx2.Request("POST", "https://api.example.com/v1/test")
    body = {"type": "error", "error": {"type": error_type, "message": message}}
    response = httpx2.Response(status_code, request=request, json=body)
    return exc_cls(message, response=response, body=body)


def make_connection_error(exc_cls, *, message: str = "connection failed"):
    request = httpx2.Request("POST", "https://api.example.com/v1/test")
    return exc_cls(message=message, request=request)
