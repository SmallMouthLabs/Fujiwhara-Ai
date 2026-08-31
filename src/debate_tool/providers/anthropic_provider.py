"""Anthropic adapter: the Claude seat's only path to the Anthropic API.

Nothing outside this module imports `anthropic` directly.
"""

from __future__ import annotations

import anthropic

from .base import Message, ProviderAdapter, ProviderError, ProviderResponse


class AnthropicAdapter(ProviderAdapter):
    name = "anthropic"

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        # No api_key argument: the SDK resolves ANTHROPIC_API_KEY (or an `ant auth
        # login` profile) from the environment on its own. `debate_tool.env.load()`
        # just has to have run first so `.env` is in that environment.
        self._client = client or anthropic.Anthropic()

    def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
    ) -> ProviderResponse:
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system is not None:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            response = self._client.messages.create(**kwargs)
        except anthropic.NotFoundError as e:
            raise ProviderError(
                f"anthropic: model not found ({model}): {e}",
                provider=self.name,
                retryable=False,
                status_code=404,
                cause=e,
            ) from e
        except anthropic.RateLimitError as e:
            raise ProviderError(
                f"anthropic: rate limited: {e}",
                provider=self.name,
                retryable=True,
                status_code=429,
                cause=e,
            ) from e
        except anthropic.APIStatusError as e:
            raise ProviderError(
                f"anthropic: request failed ({e.status_code}): {e}",
                provider=self.name,
                retryable=e.status_code >= 500,
                status_code=e.status_code,
                cause=e,
            ) from e
        except anthropic.APIConnectionError as e:
            raise ProviderError(
                f"anthropic: connection failed: {e}",
                provider=self.name,
                retryable=True,
                cause=e,
            ) from e

        text = "".join(block.text for block in response.content if block.type == "text")

        return ProviderResponse(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            raw=response,
        )
