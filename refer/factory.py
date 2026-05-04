"""
LLM factory — returns the right LLMClient subclass based on LLM_PROVIDER.

To add a new provider:
  1. Create  llm/<provider>_client.py  with a class that extends LLMClient
  2. Add an elif branch below
  3. Set  LLM_PROVIDER=<provider>  in .env
"""

import os
from llm.base import LLMClient


def get_llm_client() -> LLMClient:
    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()

    if provider == "groq":
        from llm.groq_client import GroqClient
        return GroqClient()

    elif provider == "anthropic":
        # pip install anthropic
        from llm.anthropic_client import AnthropicClient   # type: ignore[import]
        return AnthropicClient()

    elif provider in ("openai", "azure_openai"):
        # pip install openai
        from llm.openai_client import OpenAIClient          # type: ignore[import]
        return OpenAIClient(provider=provider)

    elif provider == "litellm":
        from llm.litellm_client import LiteLLMClient
        return LiteLLMClient()

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. "
            "Supported values: groq | anthropic | openai | azure_openai | litellm"
        )
