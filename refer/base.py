from abc import ABC, abstractmethod


class LLMClient(ABC):
    """
    Minimal interface for any LLM provider.

    Every implementation accepts a standard OpenAI-style messages list:
        [{"role": "system"|"user"|"assistant", "content": "..."}]
    and returns the assistant reply as a plain string.

    Adding a new provider (Anthropic, OpenAI, Azure, etc.) means creating
    a new subclass in this package and registering it in factory.py —
    nothing else changes.
    """

    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0) -> str:
        """Send messages and return the assistant reply text."""
