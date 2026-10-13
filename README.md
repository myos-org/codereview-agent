# 🔍 Code Review Agent

An autonomous agent that reviews GitHub pull requests — fetches the diff, finds bugs and
security issues, suggests refactors, and writes the review comment for you.

Built with **LangGraph**, **FastAPI** and **Streamlit**, and designed around a
**BYOK (Bring Your Own Key)** architecture: you pick the provider and paste your own API
key, so the app costs **$0** to host and run, indefinitely.

> **Status:** early scaffold. The review pipeline runs end to end; the security pass,
> structured findings and comparison mode are still to come — see [Roadmap](#roadmap).

---

## Why BYOK

Most portfolio LLM apps either burn the author's API credits or go offline when they run
out. This one never touches my key:

- The key is entered in the UI, held **in session memory only**, and passed per request
- It is **never logged, never persisted**, and never written to disk or a database
- Inputs are masked (`type="password"`), and the API models it as `SecretStr` so it stays
  out of tracebacks and `repr()`
- Drop the key and the session forgets it

The result: unlimited users, no rate-limit ceiling of mine to hit, and zero running cost.

### Optional free tier

So a first-time visitor can try it without signing up anywhere, the host can set
`FREE_TIER_API_KEY` to their own **Groq** key (free plan, so still $0). Each visitor gets
`FREE_TIER_REVIEWS_PER_SESSION` reviews (default 3) on it; after that — or as soon as
Groq rate-limits the shared key — the UI asks for the visitor's own key. A key the
visitor pastes always takes priority. Leave the variable unset and the app is pure BYOK.

## Providers

Pick a provider, pick a model, paste a key — the agent itself never changes.

| Provider | Models | Notes |
|---|---|---|
| **Groq** | GPT-OSS 120B / 20B, Qwen3.8 27B | Free tier, ~30 req/min. Fastest — the dev default |
| **Anthropic** | Claude Sonnet 5, Opus 5, Haiku 4.5 | Paid. Best review quality |
| **OpenAI** | GPT-4o, GPT-4o mini | Paid |
| **Google** | Gemini 1.5 Flash / Pro | Free tier, 15 req/min |
| **Ollama** | Llama 3.1, Qwen2.5-Coder | Local, offline, no key at all |

## Quick start

```bash
git clone github-personal:Chiragtyagi03/code-review-agent.git
cd code-review-agent

python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

streamlit run streamlit_app.py
```

Then open the sidebar, choose **Groq**, paste a free key from
[console.groq.com](https://console.groq.com), and give it a PR URL.

**Private repositories:** add a GitHub token in the sidebar (or `github_token` on the
API). A [fine-grained token](https://github.com/settings/personal-access-tokens/new) with
read-only **Pull requests** and **Contents** access to that repo is enough. It gets the
same treatment as the model key — this request only, never stored. A token also raises
GitHub's rate limit from 60 to 5,000 requests an hour.

To run the API instead:

```bash
uvicorn src.api.main:app --reload
# → http://127.0.0.1:8000/docs
```

## How it works

```
PR URL
  │
  ├─ fetch      GitHub API → diff, minus lock files and generated assets
  ├─ analyze    LLM finds bugs, security issues, smells
  └─ summarize  LLM writes the review comment
        │
        └→ findings + summary
```

Token cost is kept down before the model is ever called: generated files are filtered out
of the diff, and the prompt is truncated to a fixed character budget, largest files dropped
first.

## Layout

```
src/
  providers.py       BYOK provider factory — the only vendor-aware module
  github_client.py   PR fetching, diff filtering, prompt flattening
  agent/
    graph.py         LangGraph: fetch → analyze → summarize
    state.py         Typed graph state
    prompts.py       System prompts
  memory/store.py    Ephemeral Chroma store for follow-up questions
  api/main.py        FastAPI
streamlit_app.py     UI
```

## Roadmap

- [x] Provider factory with five backends
- [x] PR fetching with generated-file filtering
- [x] `fetch → analyze → summarize` graph
- [x] Streamlit UI + FastAPI, CI, Docker
- [ ] Structured findings (severity, file, line) instead of prose
- [ ] Dedicated security-scanning node
- [ ] Chat with Code — follow-up questions over the diff
- [ ] Comparison mode — two models on one PR, side by side
- [ ] Post the review back as a PR comment
- [ ] Evaluation harness over a fixed set of PRs

## Development

```bash
pytest -q        # tests
ruff check .     # lint
```

## License

MIT
