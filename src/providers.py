"""Provider factory for BYOK (Bring Your Own Key).

The whole point of this module: the agent never knows which vendor it is
talking to. It receives a LangChain chat model and calls it. Swapping
provider swaps only the object built here.

Keys are passed in per request and are never stored, logged, or written
to disk. Do not add logging to this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    models: tuple[str, ...]
    needs_key: bool = True
    free_tier: str = ""
    extras: dict = field(default_factory=dict)


PROVIDERS: dict[str, Provider] = {
    "groq": Provider(
        key="groq",
        label="Groq",
        models=("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"),
        free_tier="Free, ~30 req/min. Fastest option — the default for development.",
    ),
    "anthropic": Provider(
        key="anthropic",
        label="Anthropic",
        models=("claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5-20251001"),
        free_tier="Paid. Best review quality — use for the demo recording.",
    ),
    "openai": Provider(
        key="openai",
        label="OpenAI",
        models=("gpt-4o", "gpt-4o-mini"),
        free_tier="Paid.",
    ),
    "google": Provider(
        key="google",
        label="Google Gemini",
        models=("gemini-1.5-flash", "gemini-1.5-pro"),
        free_tier="Free, 15 req/min.",
    ),
    "ollama": Provider(
        key="ollama",
        label="Ollama (local)",
        models=("llama3.1", "qwen2.5-coder"),
        needs_key=False,
        free_tier="Free and fully offline. Requires Ollama running locally.",
    ),
}


def build_llm(provider: str, model: str, api_key: str | None = None, **kwargs):
    """Return a LangChain chat model for `provider`.

    `api_key` is used to construct the client and then goes out of scope with
    it. Nothing here persists it.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. Expected one of {sorted(PROVIDERS)}.")

    spec = PROVIDERS[provider]
    if spec.needs_key and not api_key:
        raise ValueError(f"{spec.label} requires an API key.")

    # Imported lazily so a missing optional dependency only breaks the
    # provider that needs it, not the whole app.
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=model, api_key=api_key, **kwargs)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, api_key=api_key, **kwargs)

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, api_key=api_key, **kwargs)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, **kwargs)

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model, **kwargs)

    raise AssertionError(f"unreachable: {provider}")
