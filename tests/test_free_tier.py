import pytest

from src.free_tier import FreeTier, is_rate_limited


def test_disabled_without_a_key(monkeypatch):
    monkeypatch.delenv("FREE_TIER_API_KEY", raising=False)
    tier = FreeTier(_env_file=None)
    assert not tier.enabled
    assert not tier.covers("groq")


def test_covers_only_its_own_provider(monkeypatch):
    monkeypatch.setenv("FREE_TIER_API_KEY", "gsk_host")
    tier = FreeTier(_env_file=None)
    assert tier.covers("groq")
    assert not tier.covers("anthropic")
    assert tier.key() == "gsk_host"
    assert "gsk_host" not in repr(tier)


class Http429(Exception):
    status_code = 429


class RateLimitError(Exception):
    pass


@pytest.mark.parametrize("exc", [Http429(), RateLimitError()])
def test_rate_limits_are_recognised(exc):
    assert is_rate_limited(exc)


def test_other_errors_are_not_rate_limits():
    assert not is_rate_limited(ValueError("bad url"))
