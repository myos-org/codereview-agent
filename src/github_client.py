"""Minimal GitHub PR reader — just enough to fetch a diff."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

PR_URL = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

# Reviewing generated files burns tokens for no insight.
SKIP = re.compile(
    r"(package-lock\.json|yarn\.lock|poetry\.lock|pnpm-lock\.yaml|\.min\.(js|css)$|"
    r"/(dist|build|vendor|node_modules)/|\.(svg|png|jpe?g|gif|ico|pdf|lock)$)"
)


@dataclass
class FileDiff:
    path: str
    additions: int
    deletions: int
    patch: str


@dataclass
class PullRequest:
    owner: str
    repo: str
    number: int
    title: str
    description: str
    files: list[FileDiff]

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


def parse_pr_url(url: str) -> tuple[str, str, int]:
    m = PR_URL.search(url)
    if not m:
        raise ValueError(f"Not a GitHub pull request URL: {url!r}")
    owner, repo, number = m.groups()
    return owner, repo, int(number)


class GitHubAccessError(ValueError):
    """The PR could not be read — private, missing, or rate limited."""


def _get(client: httpx.Client, url: str, has_token: bool, **kwargs) -> httpx.Response:
    resp = client.get(url, **kwargs)
    # GitHub answers 404, not 403, for a private repo you cannot see.
    if resp.status_code == 404:
        hint = (
            "Check the URL, and that the token can read this repository."
            if has_token
            else "If the repository is private, add a GitHub token."
        )
        raise GitHubAccessError(f"Pull request not found. {hint}")
    if resp.status_code == 401:
        raise GitHubAccessError("GitHub rejected the token — it may be expired or mistyped.")
    if resp.status_code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0":
        hint = "" if has_token else " Add a GitHub token to raise the limit to 5,000/hour."
        raise GitHubAccessError(f"GitHub API rate limit reached.{hint}")
    resp.raise_for_status()
    return resp


def fetch_pr(url: str, token: str | None = None, max_files: int = 40) -> PullRequest:
    owner, repo, number = parse_pr_url(url)

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    with httpx.Client(headers=headers, timeout=30.0) as client:
        meta = _get(client, base, has_token=bool(token)).json()
        raw_files = _get(
            client, f"{base}/files", has_token=bool(token), params={"per_page": 100}
        ).json()

    files = [
        FileDiff(
            path=f["filename"],
            additions=f.get("additions", 0),
            deletions=f.get("deletions", 0),
            patch=f.get("patch", ""),
        )
        for f in raw_files
        if f.get("patch") and not SKIP.search(f["filename"])
    ][:max_files]

    return PullRequest(
        owner=owner,
        repo=repo,
        number=number,
        title=meta.get("title", ""),
        description=meta.get("body") or "",
        files=files,
    )


def number_patch(patch: str) -> tuple[str, list[int]]:
    """Prefix each new-side line with its line number.

    Models are bad at counting lines from hunk headers, so the gutter does it
    for them. Returns the numbered patch and the numbers it contains, which
    are also the only lines GitHub accepts an inline comment on.
    """
    out: list[str] = []
    lines: list[int] = []
    n = 0
    for raw in patch.splitlines():
        if m := HUNK.match(raw):
            n = int(m.group(1))
            out.append(raw)
        elif raw.startswith("-") or raw.startswith("\\"):
            out.append(f"{'':>5} {raw}")
        else:
            out.append(f"{n:>5} {raw}")
            lines.append(n)
            n += 1
    return "\n".join(out), lines


def diff_lines(pr: PullRequest) -> dict[str, list[int]]:
    return {f.path: number_patch(f.patch)[1] for f in pr.files}


def overview(pr: PullRequest, max_description: int = 2_000) -> str:
    """The PR without its diff — enough context to write the summary."""
    parts = [f"# PR {pr.slug}: {pr.title}", ""]
    if pr.description:
        parts += ["## Description", pr.description.strip()[:max_description], ""]
    parts.append("## Files")
    parts += [f"- {f.path} (+{f.additions} -{f.deletions})" for f in pr.files]
    return "\n".join(parts)


def as_prompt_text(pr: PullRequest, max_chars: int = 60_000) -> str:
    """Flatten a PR into the text the model sees, truncated to a token budget."""
    parts = [f"# PR {pr.slug}: {pr.title}", ""]
    if pr.description:
        parts += ["## Description", pr.description.strip(), ""]

    budget = max_chars - sum(len(p) for p in parts)
    for f in pr.files:
        numbered, _ = number_patch(f.patch)
        block = f"## {f.path} (+{f.additions} -{f.deletions})\n```diff\n{numbered}\n```\n"
        if len(block) > budget:
            parts.append(f"## {f.path} — omitted, diff too large\n")
            continue
        parts.append(block)
        budget -= len(block)

    return "\n".join(parts)
