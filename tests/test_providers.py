"""Unit tests for the provider adapters.

No network calls: each test injects a fake client whose `messages.create` /
`chat.completions.create` either returns a stand-in response object or raises
a real SDK exception (built in conftest.py), so we're testing our own request
building and response/error mapping, not the providers themselves.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import openai
import pytest

from conftest import make_connection_error, make_status_error
from debate_tool.providers import AnthropicAdapter, OpenAIAdapter, get_adapter
from debate_tool.providers.base import Message, ProviderError


# --- Anthropic -----------------------------------------------------------------


def _fake_anthropic_response(*, text="hello", model="claude-sonnet-5", input_tokens=10, output_tokens=5):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        model=model,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_anthropic_generate_maps_request_and_response():
    client = MagicMock()
    client.messages.create.return_value = _fake_anthropic_response(text="the skeptic's take")
    adapter = AnthropicAdapter(client=client)

    result = adapter.generate(
        [Message(role="user", content="seed idea")],
        model="claude-sonnet-5",
        system="You are the skeptic.",
        max_tokens=500,
        temperature=0.7,
    )

    client.messages.create.assert_called_once_with(
        model="claude-sonnet-5",
        max_tokens=500,
        messages=[{"role": "user", "content": "seed idea"}],
        system="You are the skeptic.",
        temperature=0.7,
    )
    assert result.text == "the skeptic's take"
    assert result.model == "claude-sonnet-5"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_anthropic_generate_omits_absent_optional_params():
    client = MagicMock()
    client.messages.create.return_value = _fake_anthropic_response()
    adapter = AnthropicAdapter(client=client)

    adapter.generate([Message(role="user", content="hi")], model="claude-sonnet-5")

    _, kwargs = client.messages.create.call_args
    assert "system" not in kwargs
    assert "temperature" not in kwargs


def test_anthropic_generate_joins_multiple_text_blocks():
    client = MagicMock()
    response = _fake_anthropic_response()
    response.content = [
        SimpleNamespace(type="text", text="part one. "),
        SimpleNamespace(type="thinking", thinking="ignored"),
        SimpleNamespace(type="text", text="part two."),
    ]
    client.messages.create.return_value = response
    adapter = AnthropicAdapter(client=client)

    result = adapter.generate([Message(role="user", content="hi")], model="claude-sonnet-5")

    assert result.text == "part one. part two."


def test_anthropic_not_found_maps_to_provider_error_with_status():
    client = MagicMock()
    client.messages.create.side_effect = make_status_error(
        anthropic.NotFoundError, status_code=404, message="model not found", error_type="not_found_error"
    )
    adapter = AnthropicAdapter(client=client)

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="bad-model")

    err = exc_info.value
    assert err.provider == "anthropic"
    assert err.status_code == 404


def test_anthropic_rate_limit_maps_to_provider_error_with_status():
    client = MagicMock()
    client.messages.create.side_effect = make_status_error(
        anthropic.RateLimitError, status_code=429, message="rate limited", error_type="rate_limit_error"
    )
    adapter = AnthropicAdapter(client=client)

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="claude-sonnet-5")

    assert exc_info.value.status_code == 429


def test_anthropic_status_error_preserves_status_code():
    client = MagicMock()

    client.messages.create.side_effect = make_status_error(
        anthropic.APIStatusError, status_code=500, message="server error", error_type="api_error"
    )
    adapter = AnthropicAdapter(client=client)
    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="claude-sonnet-5")
    assert exc_info.value.status_code == 500

    client.messages.create.side_effect = make_status_error(
        anthropic.APIStatusError, status_code=400, message="bad request", error_type="invalid_request_error"
    )
    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="claude-sonnet-5")
    assert exc_info.value.status_code == 400


def test_anthropic_connection_error_has_no_status_code():
    client = MagicMock()
    client.messages.create.side_effect = make_connection_error(anthropic.APIConnectionError)
    adapter = AnthropicAdapter(client=client)

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="claude-sonnet-5")

    assert exc_info.value.status_code is None


# --- OpenAI ----------------------------------------------------------------------


def _fake_openai_response(*, text="hello", model="gpt-5", prompt_tokens=10, completion_tokens=5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        model=model,
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def test_openai_generate_prepends_system_as_a_message():
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_openai_response(text="the generator's take")
    adapter = OpenAIAdapter(client=client)

    result = adapter.generate(
        [Message(role="user", content="seed idea")],
        model="gpt-5",
        system="You are the generator.",
        max_tokens=500,
        temperature=0.7,
    )

    client.chat.completions.create.assert_called_once_with(
        model="gpt-5",
        messages=[
            {"role": "system", "content": "You are the generator."},
            {"role": "user", "content": "seed idea"},
        ],
        max_completion_tokens=500,
        temperature=0.7,
    )
    assert result.text == "the generator's take"
    assert result.model == "gpt-5"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_openai_sends_max_completion_tokens_not_deprecated_max_tokens():
    # Regression: GPT-5 / reasoning models reject `max_tokens` and require
    # `max_completion_tokens`. The generator seat defaults to gpt-5, so sending
    # the deprecated name would fail every generator turn.
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_openai_response()
    adapter = OpenAIAdapter(client=client)

    adapter.generate([Message(role="user", content="hi")], model="gpt-5", max_tokens=800)

    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["max_completion_tokens"] == 800
    assert "max_tokens" not in kwargs


def test_openai_generate_omits_absent_optional_params():
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_openai_response()
    adapter = OpenAIAdapter(client=client)

    adapter.generate([Message(role="user", content="hi")], model="gpt-5")

    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert "temperature" not in kwargs


def test_openai_handles_null_message_content():
    client = MagicMock()
    response = _fake_openai_response()
    response.choices[0].message.content = None
    client.chat.completions.create.return_value = response
    adapter = OpenAIAdapter(client=client)

    result = adapter.generate([Message(role="user", content="hi")], model="gpt-5")

    assert result.text == ""


def test_openai_empty_choices_maps_to_provider_error_not_indexerror():
    client = MagicMock()
    response = _fake_openai_response()
    response.choices = []  # e.g. every candidate blocked by a content filter
    client.chat.completions.create.return_value = response
    adapter = OpenAIAdapter(client=client)

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="gpt-5")

    assert exc_info.value.provider == "openai"
    assert "no choices" in str(exc_info.value)


def test_openai_not_found_maps_to_provider_error_with_status():
    client = MagicMock()
    client.chat.completions.create.side_effect = make_status_error(
        openai.NotFoundError, status_code=404, message="model not found", error_type="not_found_error"
    )
    adapter = OpenAIAdapter(client=client)

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="bad-model")

    err = exc_info.value
    assert err.provider == "openai"
    assert err.status_code == 404


def test_openai_rate_limit_maps_to_provider_error_with_status():
    client = MagicMock()
    client.chat.completions.create.side_effect = make_status_error(
        openai.RateLimitError, status_code=429, message="rate limited", error_type="rate_limit_error"
    )
    adapter = OpenAIAdapter(client=client)

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="gpt-5")

    assert exc_info.value.status_code == 429


def test_openai_connection_error_has_no_status_code():
    client = MagicMock()
    client.chat.completions.create.side_effect = make_connection_error(openai.APIConnectionError)
    adapter = OpenAIAdapter(client=client)

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate([Message(role="user", content="hi")], model="gpt-5")

    assert exc_info.value.status_code is None


# --- Factory -----------------------------------------------------------------


def test_get_adapter_returns_correct_adapter_type(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert isinstance(get_adapter("anthropic"), AnthropicAdapter)
    assert isinstance(get_adapter("openai"), OpenAIAdapter)


def test_get_adapter_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unknown provider"):
        get_adapter("gemini")
