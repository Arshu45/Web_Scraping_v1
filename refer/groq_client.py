import logging
import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from llm.base import LLMClient

logger = logging.getLogger(__name__)


class GroqClient(LLMClient):
    """LLM client backed by Groq (langchain-groq)."""

    def __init__(self, model: str | None = None):
        self._model   = model or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        self._api_key = os.getenv("GROQ_API_KEY")

    def chat(self, messages: list[dict], temperature: float = 0) -> str:
        logger.debug("LLM call | model=%s | temperature=%s | messages=%d", self._model, temperature, len(messages))
        llm = ChatGroq(
            model=self._model,
            temperature=temperature,
            api_key=self._api_key,
        )
        lc_messages = []
        for m in messages:
            role, content = m["role"], m["content"]
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
        response = llm.invoke(lc_messages).content
        logger.debug("LLM response received | length=%d chars", len(response))
        return response
