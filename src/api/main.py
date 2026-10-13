"""FastAPI surface.

The key arrives on the request and dies with it. It is never written to a
database, a log line, or a response body.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, SecretStr

from .. import free_tier
from ..agent import run_review
from ..agent.state import Finding
from ..providers import PROVIDERS, build_llm

app = FastAPI(title="Code Review Agent", version="0.1.0")


class ReviewRequest(BaseModel):
    pr_url: str = Field(..., examples=["https://github.com/psf/requests/pull/6963"])
    provider: str = Field("groq", examples=["groq"])
    model: str = Field("openai/gpt-oss-120b")
    # SecretStr keeps the value out of tracebacks and repr().
    # Optional when the server has a free tier for this provider.
    api_key: SecretStr | None = None
    # Only needed for private repos, or to lift GitHub's anonymous rate limit.
    github_token: SecretStr | None = None


class ReviewResponse(BaseModel):
    pr_url: str
    provider: str
    model: str
    summary: str
    findings: list[Finding]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/providers")
def providers() -> dict:
    return {
        k: {
            "label": p.label,
            "models": list(p.models),
            "needs_key": p.needs_key,
            "free_tier": p.free_tier,
        }
        for k, p in PROVIDERS.items()
    }


@app.post("/review", response_model=ReviewResponse)
def review(req: ReviewRequest) -> ReviewResponse:
    free = free_tier.load()
    api_key = req.api_key.get_secret_value() if req.api_key else None
    using_free = api_key is None and free.covers(req.provider)
    try:
        llm = build_llm(req.provider, req.model, api_key=free.key() if using_free else api_key)
        result = run_review(
            req.pr_url,
            llm,
            github_token=req.github_token.get_secret_value() if req.github_token else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if using_free and free_tier.is_rate_limited(exc):
            raise HTTPException(
                status_code=429,
                detail="The free tier has hit its limit. Pass your own api_key to continue.",
            ) from exc
        raise

    return ReviewResponse(
        pr_url=req.pr_url,
        provider=req.provider,
        model=req.model,
        summary=result.get("summary", ""),
        findings=result.get("findings", []),
    )
