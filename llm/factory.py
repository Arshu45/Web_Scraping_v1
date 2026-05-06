"""
LLM Factory — returns the right LLMClient subclass based on LLM_PROVIDER.

Supports automatic fallback: if the primary provider hits a rate limit (HTTP 429),
the factory retries with the next provider in the fallback chain.

Configuration (.env):
    LLM_PROVIDER=groq          # Primary provider: groq | litellm
    LLM_FALLBACK=litellm       # Fallback provider (optional)
    LLM_MODEL=llama-3.3-70b-versatile

To add a new provider:
  1. Create  llm/<provider>_client.py  with a class that extends LLMClient
  2. Add an elif branch in _build_client() below
  3. Set  LLM_PROVIDER=<provider>  in .env
"""

import logging
import os

from llm.base import LLMClient

logger = logging.getLogger(__name__)


def _build_client(provider: str) -> LLMClient:
    """Instantiate a single LLMClient for the given provider name."""
    provider = provider.lower().strip()

    if provider == "groq":
        from llm.groq_client import GroqClient
        return GroqClient()

    elif provider == "litellm":
        from llm.litellm_client import LiteLLMClient
        return LiteLLMClient()

    else:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            "Supported: groq | litellm"
        )


def get_llm_client() -> LLMClient:
    """Return the configured primary LLMClient."""
    provider = os.getenv("LLM_PROVIDER", "groq")
    logger.debug("LLM factory: building client for provider='%s'", provider)
    return _build_client(provider)


class FallbackLLMClient(LLMClient):
    """
    Wraps two clients: primary + fallback.

    On any rate-limit error (HTTP 429) from the primary, it automatically
    retries the same call using the fallback provider. All other errors
    are re-raised immediately so they surface clearly.
    """

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self._primary  = primary
        self._fallback = fallback

    def chat(self, messages: list[dict], temperature: float = 0) -> str:
        try:
            return self._primary.chat(messages, temperature)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit_exceeded" in error_str or "Rate limit" in error_str:
                logger.warning(
                    "Primary LLM rate-limited (429). Falling back to secondary provider. Error: %s",
                    error_str[:120],
                )
                return self._fallback.chat(messages, temperature)
            # Non-rate-limit error — re-raise
            raise


def get_llm_client_with_fallback() -> LLMClient:
    """
    Returns a FallbackLLMClient if LLM_FALLBACK is set, otherwise the primary client.
    
    .env example:
        LLM_PROVIDER=groq
        LLM_FALLBACK=litellm
        LLM_MODEL=llama-3.3-70b-versatile   # used by primary
        # LiteLLM fallback uses groq/llama-3.1-8b-instant by default
    """
    primary_name  = os.getenv("LLM_PROVIDER", "groq")
    fallback_name = os.getenv("LLM_FALLBACK", "").strip()

    primary = _build_client(primary_name)

    if fallback_name:
        fallback = _build_client(fallback_name)
        logger.info(
            "LLM factory: primary='%s', fallback='%s' (rate-limit auto-retry enabled)",
            primary_name, fallback_name,
        )
        return FallbackLLMClient(primary=primary, fallback=fallback)

    logger.info("LLM factory: using '%s' (no fallback configured)", primary_name)
    return primary

def get_langchain_llm(provider: str | None = None, model: str | None = None) -> any:
    """Returns a native LangChain chat model wrapper (e.g. ChatGroq or ChatOpenAI)."""
    provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower().strip()
    model = model or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "5000"))

    if provider == "groq":
        from langchain_groq import ChatGroq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set.")
        return ChatGroq(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "litellm":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("LITELLM_API_KEY") or os.getenv("GROQ_API_KEY") or "dummy"
        api_base = os.getenv("LITELLM_API_BASE")
        return ChatOpenAI(
            api_key=api_key,
            base_url=api_base,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        raise ValueError(f"Unknown LangChain LLM provider '{provider}'. Supported: groq | litellm")

