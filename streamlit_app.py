"""Streamlit UI — provider -> model -> key -> review."""

from __future__ import annotations

import streamlit as st

from src import free_tier
from src.agent import run_review
from src.providers import PROVIDERS, build_llm

SEVERITY_BADGE = {
    "security": "🔴 security",
    "bug": "🟠 bug",
    "smell": "🟡 smell",
    "nit": "⚪ nit",
}

st.set_page_config(page_title="Code Review Agent", page_icon="🔍", layout="wide")

free = free_tier.load()
st.session_state.setdefault("free_used", 0)
# Set when the provider rate-limits the shared key; stays set for the session.
st.session_state.setdefault("free_exhausted", False)

st.title("🔍 Code Review Agent")
st.caption("Paste a GitHub PR URL and review it with the model of your choice.")

with st.sidebar:
    st.header("Model")

    provider_key = st.selectbox(
        "Provider",
        options=list(PROVIDERS),
        index=list(PROVIDERS).index(free.provider) if free.enabled else 0,
        format_func=lambda k: PROVIDERS[k].label,
    )
    spec = PROVIDERS[provider_key]
    model = st.selectbox("Model", options=spec.models)

    free_left = max(free.reviews_per_session - st.session_state.free_used, 0)
    free_available = (
        free.covers(provider_key) and free_left > 0 and not st.session_state.free_exhausted
    )

    if free_available:
        total = free.reviews_per_session
        st.success(f"🎁 {free_left} of {total} free reviews left — no key needed.")
    elif free.covers(provider_key):
        st.warning("Free reviews are used up. Paste your own key to keep going — it's free.")
    elif spec.free_tier:
        st.caption(spec.free_tier)

    api_key = None
    if spec.needs_key:
        label = f"{spec.label} API key" + (" (optional)" if free_available else "")
        api_key = st.text_input(label, type="password")
        st.caption(
            "🔒 Used only for this request and held in session memory. "
            "Never logged, never stored, never sent anywhere but the provider."
        )

    st.header("GitHub")
    github_token = st.text_input(
        "Personal access token (optional)",
        type="password",
        help="Needed for private repositories. A fine-grained token with read-only "
        "Pull requests and Contents access on the repo is enough.",
    )
    st.caption("🔒 Same rules as the API key: this request only, never stored.")

pr_url = st.text_input("Pull request URL", placeholder="https://github.com/owner/repo/pull/123")

if st.button("Review", type="primary", disabled=not pr_url):
    # The visitor's own key always wins; the shared one is only a fallback.
    using_free = spec.needs_key and not api_key and free_available
    if spec.needs_key and not api_key and not using_free:
        st.error(f"Enter your {spec.label} API key to continue.")
        st.stop()

    with st.spinner("Fetching the diff and reviewing…"):
        try:
            llm = build_llm(provider_key, model, api_key=free.key() if using_free else api_key)
            result = run_review(pr_url, llm, github_token=github_token or None)
        except Exception as exc:  # surfaced to the user, not logged
            if using_free and free_tier.is_rate_limited(exc):
                st.session_state.free_exhausted = True
                st.warning(
                    "The free tier has hit its limit for now. Paste your own "
                    f"{spec.label} key in the sidebar to continue."
                )
                st.stop()
            st.error(f"{type(exc).__name__}: {exc}")
            st.stop()

    if using_free:
        st.session_state.free_used += 1

    st.subheader("Review")
    st.markdown(result.get("summary", "_No summary produced._"))

    findings = result.get("findings", [])
    st.subheader(f"Findings ({len(findings)})")
    if not findings:
        st.success("Nothing worth flagging.")
    for f in findings:
        where = f"{f.file}:{f.line}" if f.line else f.file
        with st.expander(f"{SEVERITY_BADGE[f.severity]} `{where}` — {f.summary}"):
            st.markdown(f.suggestion)
