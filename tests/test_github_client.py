import httpx
import pytest

from src.github_client import SKIP, GitHubAccessError, _get, parse_pr_url


def test_parses_a_standard_pr_url():
    assert parse_pr_url("https://github.com/psf/requests/pull/6963") == ("psf", "requests", 6963)


def test_rejects_a_non_pr_url():
    with pytest.raises(ValueError, match="Not a GitHub pull request URL"):
        parse_pr_url("https://github.com/psf/requests")


@pytest.mark.parametrize(
    "path",
    ["package-lock.json", "web/dist/app.js", "assets/logo.svg", "app.min.js"],
)
def test_generated_files_are_skipped(path):
    assert SKIP.search(path)


def test_source_files_are_not_skipped():
    assert not SKIP.search("src/agent/graph.py")


def _client(status: int, headers: dict | None = None) -> httpx.Client:
    transport = httpx.MockTransport(lambda req: httpx.Response(status, headers=headers))
    return httpx.Client(transport=transport)


def test_private_repo_without_a_token_asks_for_one():
    with pytest.raises(GitHubAccessError, match="add a GitHub token"):
        _get(_client(404), "https://api.github.com/x", has_token=False)


def test_404_with_a_token_points_at_token_scope():
    with pytest.raises(GitHubAccessError, match="token can read this repository"):
        _get(_client(404), "https://api.github.com/x", has_token=True)


def test_bad_token_is_reported():
    with pytest.raises(GitHubAccessError, match="rejected the token"):
        _get(_client(401), "https://api.github.com/x", has_token=True)


def test_rate_limit_suggests_a_token():
    client = _client(403, {"x-ratelimit-remaining": "0"})
    with pytest.raises(GitHubAccessError, match="5,000/hour"):
        _get(client, "https://api.github.com/x", has_token=False)
