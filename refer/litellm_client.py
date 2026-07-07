import logging
import os
import litellm

from llm.base import LLMClient

logger = logging.getLogger(__name__)


class LiteLLMClient(LLMClient):
    """LLM client backed by LiteLLM — supports 100+ providers via a unified API."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ):
        self._model = model or os.getenv("LLM_MODEL")
        self._api_key = api_key or os.getenv("LITELLM_API_KEY")
        self._api_base = api_base or os.getenv("LITELLM_API_BASE")

    def chat(self, messages: list[dict], temperature: float = 0) -> str:
        logger.debug(
            "LiteLLM call | model=%s | temperature=%s | messages=%d",
            self._model, temperature, len(messages),
        )

        # Build completion kwargs
        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }

        # Add optional api_key if provided
        if self._api_key:
            kwargs["api_key"] = self._api_key

        # Add optional api_base if provided
        if self._api_base:
            kwargs["api_base"] = self._api_base

        response = litellm.completion(**kwargs)
        reply = response.choices[0].message.content
        logger.debug("LiteLLM response received | length=%d chars", len(reply))
        return reply
