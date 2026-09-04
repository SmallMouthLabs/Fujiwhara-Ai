"""Provider adapters behind one common interface.

The engine and seat config refer to providers by name ("anthropic", "openai").
`get_adapter` is the only place that name gets resolved to a concrete adapter
class, so adding a third provider later (see docs/DECISIONS.md O3) means adding
one entry here, not touching the engine.
"""

from __future__ import annotations

from .anthropic_provider import AnthropicAdapter
from .base import Message, ProviderAdapter, ProviderError, ProviderResponse
from .openai_provider import OpenAIAdapter

_ADAPTERS: dict[str, type[ProviderAdapter]] = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
}

#: Provider names `get_adapter` recognizes, exposed so config loading (persona_config.py)
#: can validate a `provider` field at load time without constructing a real adapter (which
#: may eagerly require an API key, as the OpenAI SDK does).
KNOWN_PROVIDERS: frozenset[str] = frozenset(_ADAPTERS)


def get_adapter(provider: str) -> ProviderAdapter:
    """Construct the adapter for a provider name from seat config.

    Raises ValueError for an unknown provider name, since that's a config
    mistake the caller should fix, not something to swallow.
    """
    try:
        adapter_cls = _ADAPTERS[provider]
    except KeyError:
        known = ", ".join(sorted(_ADAPTERS))
        raise ValueError(f"unknown provider {provider!r}; known providers: {known}") from None
    return adapter_cls()


__all__ = [
    "AnthropicAdapter",
    "KNOWN_PROVIDERS",
    "Message",
    "OpenAIAdapter",
    "ProviderAdapter",
    "ProviderError",
    "ProviderResponse",
    "get_adapter",
]
