"""OpenAI adapter: the ChatGPT seat's only path to the OpenAI API.

Nothing outside this module imports `openai` directly.
"""

from __future__ import annotations

import openai

from .base import Message, ProviderAdapter, ProviderError, ProviderResponse


class OpenAIAdapter(ProviderAdapter):
    name = "openai"

    def __init__(self, client: openai.OpenAI | None = None) -> None:
        # No api_key argument: the SDK resolves OPENAI_API_KEY from the environment
        # on its own. `debate_tool.env.load()` just has to have run first so `.env`
        # is in that environment.
        self._client = client or openai.OpenAI()

    def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
    ) -> ProviderResponse:
        # Unlike Anthropic, OpenAI's Chat Completions API takes "system" as a
        # message role rather than a top-level parameter, so it's prepended here.
        chat_messages: list[dict] = []
        if system is not None:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend({"role": m.role, "content": m.content} for m in messages)

        kwargs: dict = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            response = self._client.chat.completions.create(**kwargs)
        except openai.NotFoundError as e:
            raise ProviderError(
                f"openai: model not found ({model}): {e}",
                provider=self.name,
                retryable=False,
                status_code=404,
                cause=e,
            ) from e
        except openai.RateLimitError as e:
            raise ProviderError(
                f"openai: rate limited: {e}",
                provider=self.name,
                retryable=True,
                status_code=429,
                cause=e,
            ) from e
        except openai.APIStatusError as e:
            raise ProviderError(
                f"openai: request failed ({e.status_code}): {e}",
                provider=self.name,
                retryable=e.status_code >= 500,
                status_code=e.status_code,
                cause=e,
            ) from e
        except openai.APIConnectionError as e:
            raise ProviderError(
                f"openai: connection failed: {e}",
                provider=self.name,
                retryable=True,
                cause=e,
            ) from e

        choice = response.choices[0]

        return ProviderResponse(
            text=choice.message.content or "",
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            raw=response,
        )
