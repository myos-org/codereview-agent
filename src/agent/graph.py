"""The review agent.

Deliberately a small graph: fetch -> analyze -> summarize. Milestone 2 in the
roadmap adds the security pass and the retrieval node; the shape below is what
those hang off.
"""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from ..github_client import as_prompt_text, diff_lines, fetch_pr, overview
from .prompts import REVIEWER_SYSTEM, SUMMARY_SYSTEM
from .state import SEVERITY_ORDER, Finding, ReviewOutput, ReviewState


def ground(findings: list[Finding], lines: dict[str, list[int]]) -> list[Finding]:
    """Keep only findings that point at something the diff actually contains.

    A finding on a file the PR does not touch is a hallucination and is
    dropped. A line outside the diff is cleared rather than trusted, so the
    finding survives but will never become a misplaced inline comment.
    """
    kept = []
    for f in findings:
        if f.file not in lines:
            continue
        if f.line is not None and f.line not in lines[f.file]:
            f = f.model_copy(update={"line": None})
        kept.append(f)
    return sorted(kept, key=lambda f: (SEVERITY_ORDER.index(f.severity), f.file, f.line or 0))


def build_review_graph(llm, github_token: str | None = None):
    """Compile the review graph around an already-constructed chat model.

    The GitHub token lives in this closure, not in the graph state, so it is
    never part of anything the graph returns.
    """
    reviewer = llm.with_structured_output(ReviewOutput)

    def fetch(state: ReviewState) -> ReviewState:
        pr = fetch_pr(state["pr_url"], token=github_token)
        return {
            "pr_overview": overview(pr),
            "diff_text": as_prompt_text(pr),
            "diff_lines": diff_lines(pr),
        }

    def analyze(state: ReviewState) -> ReviewState:
        diff = HumanMessage(content=state["diff_text"])
        out = reviewer.invoke([SystemMessage(content=REVIEWER_SYSTEM), diff])
        findings = ground(out.findings, state["diff_lines"])
        # Recorded as a plain exchange so a follow-up chat can build on it.
        answer = AIMessage(content=_as_json(findings))
        return {"findings": findings, "messages": [diff, answer]}

    def summarize(state: ReviewState) -> ReviewState:
        msg = llm.invoke(
            [
                SystemMessage(content=SUMMARY_SYSTEM),
                HumanMessage(
                    content=f"{state['pr_overview']}\n\n## Findings\n"
                    f"{_as_json(state['findings'])}"
                ),
            ]
        )
        return {"summary": msg.content, "messages": [msg]}

    g = StateGraph(ReviewState)
    g.add_node("fetch", fetch)
    g.add_node("analyze", analyze)
    g.add_node("summarize", summarize)

    g.add_edge(START, "fetch")
    g.add_edge("fetch", "analyze")
    g.add_edge("analyze", "summarize")
    g.add_edge("summarize", END)

    return g.compile()


def _as_json(findings: list[Finding]) -> str:
    return json.dumps([f.model_dump() for f in findings], indent=2)


def run_review(pr_url: str, llm, github_token: str | None = None) -> ReviewState:
    return build_review_graph(llm, github_token).invoke({"pr_url": pr_url})
