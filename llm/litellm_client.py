import logging
import os
import litellm

from llm.base import LLMClient

logger = logging.getLogger(__name__)

# Suppress litellm's verbose startup banners
litellm.suppress_debug_info = True


class LiteLLMClient(LLMClient):
    """LLM client backed by LiteLLM — supports 100+ providers via a unified API.

    Configured via environment variables:
        LLM_MODEL       e.g. "groq/llama-3.1-8b-instant"  or  "ollama/llama3"
        LITELLM_API_KEY Optional API key (provider-specific)
        LITELLM_API_BASE Optional base URL (e.g. for local Ollama)
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ):
        self._model    = model   or os.getenv("LLM_MODEL", "groq/llama-3.1-8b-instant")
        self._api_key  = api_key or os.getenv("LITELLM_API_KEY") or os.getenv("GROQ_API_KEY")
        self._api_base = api_base or os.getenv("LITELLM_API_BASE")

    def chat(self, messages: list[dict], temperature: float = 0) -> str:
        logger.debug("LiteLLM call | model=%s | msgs=%d", self._model, len(messages))
        kwargs: dict = {
            "model":       self._model,
            "messages":    messages,
            "temperature": temperature,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._api_base:
            kwargs["api_base"] = self._api_base

        response = litellm.completion(**kwargs)
        reply = response.choices[0].message.content
        logger.debug("LiteLLM response | length=%d chars", len(reply))
        return reply
