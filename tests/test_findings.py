from langchain_core.messages import AIMessage

from src.agent import graph as graph_module
from src.agent.graph import ground, run_review
from src.agent.state import Finding, ReviewOutput
from src.github_client import FileDiff, PullRequest, number_patch

PATCH = """@@ -10,4 +10,5 @@ def load():
 a = 1
-b = 2
+b = 3
+c = 4
 return a
\\ No newline at end of file"""


def finding(**kw) -> Finding:
    base = {"file": "app.py", "line": 11, "severity": "bug", "summary": "s", "suggestion": "x"}
    return Finding(**{**base, **kw})


def test_number_patch_numbers_new_side_lines_only():
    text, lines = number_patch(PATCH)
    assert lines == [10, 11, 12, 13]
    assert "   11 +b = 3" in text
    assert "      -b = 2" in text  # removed lines carry no number


def test_number_patch_follows_each_hunk_header():
    _, lines = number_patch("@@ -1 +1 @@\n+x\n@@ -50,2 +60,2 @@\n y\n+z")
    assert lines == [1, 60, 61]


def test_ground_drops_findings_on_files_outside_the_pr():
    assert ground([finding(file="elsewhere.py")], {"app.py": [11]}) == []


def test_ground_clears_lines_outside_the_diff():
    [kept] = ground([finding(line=999)], {"app.py": [11]})
    assert kept.line is None


def test_ground_sorts_most_severe_first():
    kept = ground(
        [finding(severity="nit"), finding(severity="security"), finding(severity="bug")],
        {"app.py": [11]},
    )
    assert [f.severity for f in kept] == ["security", "bug", "nit"]


class FakeLLM:
    """Returns canned structured output and a canned summary."""

    def __init__(self, output: ReviewOutput):
        self.output = output

    def with_structured_output(self, schema):
        assert schema is ReviewOutput
        return self

    def invoke(self, messages):
        if "Write the opening" in messages[0].content:
            return AIMessage(content="Looks fine apart from one bug.")
        return self.output


def test_review_runs_end_to_end(monkeypatch):
    pr = PullRequest("o", "r", 1, "Tweak", "", [FileDiff("app.py", 2, 1, PATCH)])
    seen = {}

    def fake_fetch(url, token=None):
        seen["token"] = token
        return pr

    monkeypatch.setattr(graph_module, "fetch_pr", fake_fetch)

    llm = FakeLLM(ReviewOutput(findings=[finding(), finding(file="ghost.py")]))
    result = run_review("https://github.com/o/r/pull/1", llm, github_token="ghp_x")

    assert seen["token"] == "ghp_x"
    assert "ghp_x" not in repr(result)  # the token never enters graph state
    assert result["summary"] == "Looks fine apart from one bug."
    assert [(f.file, f.line) for f in result["findings"]] == [("app.py", 11)]
