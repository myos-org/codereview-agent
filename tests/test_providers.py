import pytest

from src.providers import PROVIDERS, build_llm


def test_every_provider_declares_at_least_one_model():
    for key, spec in PROVIDERS.items():
        assert spec.models, f"{key} declares no models"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="Unknown provider"):
        build_llm("not-a-provider", "whatever", api_key="x")


def test_key_required_providers_reject_a_missing_key():
    with pytest.raises(ValueError, match="requires an API key"):
        build_llm("groq", "openai/gpt-oss-120b", api_key=None)


def test_ollama_needs_no_key():
    assert PROVIDERS["ollama"].needs_key is False
