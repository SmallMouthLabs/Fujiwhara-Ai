"""Shared test helpers.

`make_status_error`/`make_connection_error`: both the anthropic and openai SDKs
(Stainless-generated) require a genuine httpx2 Response/Request to build their
exception types, so tests build one instead of guessing at a simpler constructor.

`FakeAdapter`: a `ProviderAdapter` test double for engine tests, so the debate
loop can be exercised without any network call. Supports two scripting modes:
a FIFO queue of response strings (`FakeAdapter(["first", "second"])`), or a
callable given the request and asked to produce the response text
(`FakeAdapter(responder=lambda messages, **kw: "...")`) for responses that need
to depend on what was actually sent. Every call is recorded in `.calls` for
assertions on what the engine actually sent.
"""

from __future__ import annotations

from typing import Callable

import httpx2

from debate_tool.providers.base import Message, ProviderAdapter, ProviderResponse


class FakeAdapter(ProviderAdapter):
    name = "fake"

    def __init__(
        self,
        responses: list[str] | None = None,
        *,
        responder: Callable[..., str] | None = None,
    ) -> None:
        if responses is not None and responder is not None:
            raise ValueError("pass either responses or responder, not both")
        self._responses = list(responses) if responses is not None else None
        self._responder = responder
        self.calls: list[dict] = []

    def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
    ) -> ProviderResponse:
        self.calls.append(
            {
                "messages": list(messages),
                "model": model,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        if self._responder is not None:
            text = self._responder(messages, model=model, system=system)
        elif self._responses:
            text = self._responses.pop(0)
        else:
            raise AssertionError("FakeAdapter.generate called with no scripted response left")

        return ProviderResponse(text=text, model=model, input_tokens=10, output_tokens=10)


def make_status_error(exc_cls, *, status_code: int, message: str, error_type: str):
    request = httpx2.Request("POST", "https://api.example.com/v1/test")
    body = {"type": "error", "error": {"type": error_type, "message": message}}
    response = httpx2.Response(status_code, request=request, json=body)
    return exc_cls(message, response=response, body=body)


def make_connection_error(exc_cls, *, message: str = "connection failed"):
    request = httpx2.Request("POST", "https://api.example.com/v1/test")
    return exc_cls(message=message, request=request)
