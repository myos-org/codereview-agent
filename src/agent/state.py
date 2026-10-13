from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

Severity = Literal["security", "bug", "smell", "nit"]

# Most severe first — the order findings are sorted and rendered in.
SEVERITY_ORDER: tuple[Severity, ...] = ("security", "bug", "smell", "nit")


class Finding(BaseModel):
    """One problem in the diff. This is the schema the model fills in."""

    file: str = Field(description="Path of the file, exactly as in its '## <path>' heading.")
    line: int | None = Field(
        None,
        description="Line number from the left gutter of the diff. Null if no single line fits.",
    )
    severity: Severity
    summary: str = Field(description="One sentence stating the defect.")
    suggestion: str = Field(description="A concrete fix, with code where it helps.")


class ReviewOutput(BaseModel):
    """Structured output of the analyze step."""

    findings: list[Finding] = Field(
        default_factory=list,
        description="Real problems only. Empty if the diff is fine.",
    )


class ReviewState(TypedDict, total=False):
    """What flows through the graph.

    `messages` keeps the conversation so "Chat with Code" can continue from a
    finished review instead of re-sending the whole diff.
    """

    pr_url: str
    pr_overview: str
    diff_text: str
    # path -> new-side line numbers a finding (or an inline PR comment) may point at
    diff_lines: dict[str, list[int]]
    findings: list[Finding]
    summary: str
    messages: Annotated[list[BaseMessage], add_messages]
