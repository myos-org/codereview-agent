"""Free tier: a host-owned key that visitors can use before bringing their own.

Off unless FREE_TIER_API_KEY is set. It covers exactly one provider — Groq by
default, whose free plan costs the host nothing — and every visitor gets a
small number of reviews on it. When those run out, or the provider itself
rate-limits the shared key, the UI asks for the visitor's own key instead.

Like providers.py, this module never logs a key.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class FreeTier(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FREE_TIER_", extra="ignore")

    api_key: SecretStr | None = None
    provider: str = "groq"
    reviews_per_session: int = 3

    @property
    def enabled(self) -> bool:
        return self.api_key is not None and bool(self.api_key.get_secret_value())

    def covers(self, provider: str) -> bool:
        return self.enabled and provider == self.provider

    def key(self) -> str:
        assert self.api_key is not None
        return self.api_key.get_secret_value()


def load() -> FreeTier:
    return FreeTier()


def is_rate_limited(exc: BaseException) -> bool:
    """True if a provider refused the call for quota reasons.

    Each SDK has its own exception class, but they all carry an HTTP 429 or
    a recognisable name, so this avoids importing every vendor's SDK.
    """
    if getattr(exc, "status_code", None) == 429:
        return True
    name = type(exc).__name__
    return name in {"RateLimitError", "ResourceExhausted", "TooManyRequests"}
