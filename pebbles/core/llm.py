"""LLMAdapter Protocol + Anthropic reference impl.

Abstracts LLM provider so Rater, Presence's drafter, and any future primitive
can swap providers without changing call sites.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class LLMResponse:
    """Provider-agnostic completion response."""

    text: str
    usage: Optional[dict] = None  # {"input_tokens": N, "output_tokens": M}
    model: Optional[str] = None
    raw: Optional[dict] = field(default=None)  # provider-specific full response, opaque


class LLMAdapter(Protocol):
    """Protocol for LLM completion providers."""

    def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs,
    ) -> LLMResponse:
        """Single-shot completion.

        Args:
            system: System prompt.
            messages: [{"role": "user"|"assistant", "content": "..."}, ...]
            max_tokens: Max output tokens.
            temperature: Sampling temperature.
            **kwargs: provider-specific extras passed through.
        """
        ...

    def complete_json(
        self,
        system: str,
        messages: list[dict],
        schema: Optional[dict] = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict:
        """JSON-mode completion. Returns parsed dict.

        If `schema` is provided, the adapter may inject schema-instructions into
        the system prompt (provider-specific). Caller is responsible for the
        prompt's content beyond that.

        Raises ValueError if response is not parseable JSON after strip-and-retry.
        """
        ...


class AnthropicAdapter:
    """Anthropic Claude reference impl.

    Requires `anthropic` package. By default uses claude-sonnet-4-6.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "AnthropicAdapter requires `anthropic` package. "
                "Install: pip install anthropic"
            ) from e
        self._anthropic_module = anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(self, system, messages, max_tokens=4096, temperature=1.0, **kwargs) -> LLMResponse:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
            **kwargs,
        )
        text = response.content[0].text if response.content else ""
        logger.info(
            f"[anthropic] Tokens: {response.usage.input_tokens} in / "
            f"{response.usage.output_tokens} out | model: {response.model}"
        )
        return LLMResponse(
            text=text,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            model=response.model,
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def complete_json(self, system, messages, schema=None, max_tokens=4096, **kwargs) -> dict:
        json_system = system
        if schema is not None:
            json_system = (
                f"{system}\n\n"
                f"Respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}\n"
                f"Output ONLY the JSON object — no prose, no code fences."
            )
        else:
            json_system = (
                f"{system}\n\nRespond with valid JSON only — no prose, no code fences."
            )

        response = self.complete(
            system=json_system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=kwargs.pop("temperature", 0.0),  # JSON mode benefits from low temp
            **kwargs,
        )

        text = response.text.strip()
        # Strip code fences if model added them
        if text.startswith("```"):
            lines = text.split("\n")
            # remove first line (```json or ```) and last line (```)
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {text[:200]}")
            raise ValueError(f"LLM response was not valid JSON: {e}") from e


class OllamaAdapter:
    """Ollama local model adapter. Zero API cost.

    Uses the Ollama REST API at http://localhost:11434.
    Recommended model for relevance scoring: qwen2.5:7b
    """

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(self, system, messages, max_tokens=4096, temperature=0.0, **kwargs) -> LLMResponse:
        import urllib.request
        prompt_messages = [{"role": "system", "content": system}] + messages
        payload = json.dumps({
            "model": self.model,
            "messages": prompt_messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        text = data.get("message", {}).get("content", "")
        in_tok = data.get("prompt_eval_count", 0)
        out_tok = data.get("eval_count", 0)
        logger.info(f"[ollama:{self.model}] Tokens: {in_tok} in / {out_tok} out")
        return LLMResponse(text=text, usage={"input_tokens": in_tok, "output_tokens": out_tok}, model=self.model)

    def complete_json(self, system, messages, schema=None, max_tokens=4096, **kwargs) -> dict:
        json_system = system
        if schema is not None:
            json_system = (
                f"{system}\n\n"
                f"Respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}\n"
                f"Output ONLY the JSON object — no prose, no code fences."
            )
        else:
            json_system = f"{system}\n\nRespond with valid JSON only — no prose, no code fences."

        response = self.complete(system=json_system, messages=messages, max_tokens=max_tokens,
                                 temperature=kwargs.pop("temperature", 0.0), **kwargs)
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"[ollama] Failed to parse JSON: {text[:200]}")
            raise ValueError(f"LLM response was not valid JSON: {e}") from e
