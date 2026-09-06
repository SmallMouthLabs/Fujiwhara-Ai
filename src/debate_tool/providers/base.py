"""The common interface every model provider adapter implements.

This is the seam the whole engine depends on: a seat talks to a `ProviderAdapter`,
never to the Anthropic or OpenAI SDKs directly. That is what lets the two anchor
seats sit on different underlying models (the main defense against mode collapse,
see CLAUDE.md) without the engine caring which model is which.

Nothing here knows about seats, turns, personas, or the uptake rule. This module is
plain request/response plumbing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    """One turn in a conversation, from the caller's point of view.

    System prompts are passed separately (see `ProviderAdapter.generate`), not as a
    message, because the two providers disagree on whether "system" is a message
    role (OpenAI) or a top-level parameter (Anthropic). Normalizing to the stricter
    of the two keeps every adapter symmetric.
    """

    role: Role
    content: str


@dataclass(frozen=True)
class ProviderResponse:
    """The normalized result of one `generate` call, regardless of provider."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    raw: object = field(default=None, repr=False, compare=False)


class ProviderError(Exception):
    """Raised for any provider failure, wrapping the provider-specific exception.

    The engine catches this one type; it does not need to know that Anthropic and
    OpenAI raise different exception hierarchies for "rate limited" or "bad request".

    Note on retries: this error carries no `retryable` flag on purpose. Both SDKs
    already retry transient failures (429, >=500, connection errors) with
    exponential backoff on their own (`max_retries`, default 2), so by the time a
    ProviderError surfaces here the automatic retries are exhausted or the error
    was never retryable. Adding a second retry layer keyed on a flag here would
    just double-retry. `status_code` is kept because it's genuinely useful for
    reporting and for a caller that wants to branch (e.g. a 404 bad-model-id vs a
    401 bad-key), not to drive retries.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.__cause__ = cause


class ProviderAdapter(ABC):
    """Common interface every model provider adapter must implement."""

    #: Short name used in config and error messages, e.g. "anthropic", "openai".
    name: str

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
    ) -> ProviderResponse:
        """Send a conversation to the model and return its reply.

        `messages` is that seat's own history only (the engine keeps per-seat
        histories genuinely separate, per CLAUDE.md); adapters never merge or see
        another seat's conversation. `model` is required and always comes from
        seat config, never a hardcoded default here, so swapping a seat's model is
        a config change (see docs/DECISIONS.md D11).
        """
        raise NotImplementedError
