from abc import ABC, abstractmethod
from typing import Optional


class LLMBackend(ABC):
    """Abstract base for all LLM backends."""

    @abstractmethod
    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class OpenAIBackend(LLMBackend):
    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai")
        import os
        self.client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
        self.model = model

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self.client.chat.completions.create(model=self.model, messages=messages)
        return resp.choices[0].message.content.strip()

    def name(self) -> str:
        return f"openai/{self.model}"


class AnthropicBackend(LLMBackend):
    def __init__(self, model: str = "claude-sonnet-4-5", api_key: Optional[str] = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package required: pip install anthropic")
        import os
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        kwargs = {"model": self.model, "max_tokens": 2048,
                  "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        resp = self.client.messages.create(**kwargs)
        return resp.content[0].text.strip()

    def name(self) -> str:
        return f"anthropic/{self.model}"


class GeminiBackend(LLMBackend):
    def __init__(self, model: str = "gemini-2.0-flash", api_key: Optional[str] = None):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package required: pip install google-generativeai")
        import os
        genai.configure(api_key=api_key or os.environ["GEMINI_API_KEY"])
        self.model_obj = genai.GenerativeModel(model)
        self._model_name = model

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        resp = self.model_obj.generate_content(full_prompt)
        return resp.text.strip()

    def name(self) -> str:
        return f"gemini/{self._model_name}"


def get_backend(provider: str, model: Optional[str] = None, api_key: Optional[str] = None) -> LLMBackend:
    """Factory — returns the right backend from a provider string."""
    p = provider.lower()
    if p in ("openai", "gpt"):
        return OpenAIBackend(model=model or "gpt-4o", api_key=api_key)
    elif p in ("anthropic", "claude"):
        return AnthropicBackend(model=model or "claude-sonnet-4-5", api_key=api_key)
    elif p in ("gemini", "google"):
        return GeminiBackend(model=model or "gemini-2.0-flash", api_key=api_key)
    else:
        raise ValueError(f"Unknown provider '{provider}'. Choose: openai, anthropic, gemini")
