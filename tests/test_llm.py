"""Tests for pebbles.core.llm — covers the AnthropicAdapter without hitting the API.

The actual Anthropic API call is mocked. We verify:
- Adapter constructs without an API key (uses env)
- complete() returns LLMResponse with expected fields
- complete_json() injects JSON instructions and parses response
- complete_json() handles code fences in model output
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from pebbles.core.llm import DEFAULT_MODEL, AnthropicAdapter, LLMResponse


@pytest.fixture
def fake_anthropic_response():
    """Build a fake Anthropic SDK response object."""
    resp = MagicMock()
    resp.content = [MagicMock(text="hello world")]
    resp.usage = MagicMock(input_tokens=10, output_tokens=5)
    resp.model = "claude-sonnet-4-6"
    resp.model_dump = lambda: {"id": "msg_test", "content": [{"text": "hello world"}]}
    return resp


def test_adapter_default_model():
    with patch("anthropic.Anthropic"):
        a = AnthropicAdapter(api_key="fake")
    assert a.model == DEFAULT_MODEL


def test_adapter_custom_model():
    with patch("anthropic.Anthropic"):
        a = AnthropicAdapter(api_key="fake", model="claude-haiku-4-5")
    assert a.model == "claude-haiku-4-5"


def test_complete_returns_llm_response(fake_anthropic_response):
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_anthropic_response
        mock_anthropic.return_value = mock_client

        a = AnthropicAdapter(api_key="fake")
        response = a.complete(
            system="be helpful",
            messages=[{"role": "user", "content": "hi"}],
        )

    assert isinstance(response, LLMResponse)
    assert response.text == "hello world"
    assert response.usage == {"input_tokens": 10, "output_tokens": 5}
    assert response.model == "claude-sonnet-4-6"


def test_complete_passes_system_and_messages(fake_anthropic_response):
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_anthropic_response
        mock_anthropic.return_value = mock_client

        a = AnthropicAdapter(api_key="fake")
        a.complete(system="SYS", messages=[{"role": "user", "content": "MSG"}])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "SYS"
        assert call_kwargs["messages"] == [{"role": "user", "content": "MSG"}]
        assert call_kwargs["model"] == DEFAULT_MODEL


def test_complete_json_parses_clean_json():
    fake = MagicMock()
    fake.content = [MagicMock(text='{"score": 0.81, "notes": "good"}')]
    fake.usage = MagicMock(input_tokens=1, output_tokens=1)
    fake.model = "x"
    fake.model_dump = lambda: {}

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake
        mock_anthropic.return_value = mock_client

        a = AnthropicAdapter(api_key="fake")
        result = a.complete_json(system="judge this", messages=[{"role": "user", "content": "x"}])

    assert result == {"score": 0.81, "notes": "good"}


def test_complete_json_strips_code_fences():
    """Models sometimes wrap JSON in ```json ... ``` despite instructions not to."""
    fake = MagicMock()
    fake.content = [MagicMock(text='```json\n{"score": 0.5}\n```')]
    fake.usage = MagicMock(input_tokens=1, output_tokens=1)
    fake.model = "x"
    fake.model_dump = lambda: {}

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake
        mock_anthropic.return_value = mock_client

        a = AnthropicAdapter(api_key="fake")
        result = a.complete_json(system="x", messages=[{"role": "user", "content": "x"}])

    assert result == {"score": 0.5}


def test_complete_json_raises_on_invalid_json():
    fake = MagicMock()
    fake.content = [MagicMock(text="not json at all")]
    fake.usage = MagicMock(input_tokens=1, output_tokens=1)
    fake.model = "x"
    fake.model_dump = lambda: {}

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake
        mock_anthropic.return_value = mock_client

        a = AnthropicAdapter(api_key="fake")
        with pytest.raises(ValueError, match="not valid JSON"):
            a.complete_json(system="x", messages=[{"role": "user", "content": "x"}])


def test_complete_json_with_schema_appends_to_system():
    fake = MagicMock()
    fake.content = [MagicMock(text='{"x": 1}')]
    fake.usage = MagicMock(input_tokens=1, output_tokens=1)
    fake.model = "x"
    fake.model_dump = lambda: {}

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake
        mock_anthropic.return_value = mock_client

        a = AnthropicAdapter(api_key="fake")
        a.complete_json(
            system="rate it",
            messages=[{"role": "user", "content": "x"}],
            schema={"x": "int"},
        )

        sent_system = mock_client.messages.create.call_args.kwargs["system"]
        assert "rate it" in sent_system
        assert '"x": "int"' in sent_system
        assert "JSON" in sent_system


def test_adapter_import_error_message():
    """If anthropic isn't installed, raise a helpful ImportError."""
    import sys

    # Temporarily make anthropic unavailable
    saved = sys.modules.pop("anthropic", None)
    sys.modules["anthropic"] = None  # type: ignore[assignment]
    try:
        with pytest.raises(ImportError, match="pip install anthropic"):
            AnthropicAdapter(api_key="fake")
    finally:
        if saved is not None:
            sys.modules["anthropic"] = saved
        else:
            sys.modules.pop("anthropic", None)
