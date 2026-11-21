"""Live suite (`D315`): a real model drives the tool loop, skipped unless
HOTDOCS_LIVE=1. Never part of a bootstrap, a gate, or `hotdocs verify`."""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-tool-endpoint"))
import llm_tool_endpoint  # noqa: E402

MODEL = os.environ.get("HOTDOCS_LIVE_MODEL", "claude-cli:claude-opus-5-5")
pytestmark = pytest.mark.skipif(os.environ.get("HOTDOCS_LIVE") != "1", reason="live suite: set HOTDOCS_LIVE=1")

TOOLS = [
    {"name": "write_note", "description": "Store a note.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "finish", "description": "Call when done.",
     "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]


def test_model_calls_tools_and_finishes(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("The project codeword is ZEBRA-4417.\n")
    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        return ("ok", False)

    os.chdir(tmp_path)
    result = llm_tool_endpoint.run_tool_loop(
        "You are a test agent. Use only the tools provided.",
        "Call write_note with the text 'hello', then call finish with summary 'done'. "
        "If you were given any project codeword, include it in the note instead.",
        MODEL, TOOLS, execute, max_turns=6, wall_seconds=600,
    )
    assert result.stop == "end_turn", (result.stop, result.model_call_error)
    assert ("write_note", {"text": "hello"}) in calls
    assert [n for n, _ in calls][-1] == "finish"
    assert "ZEBRA-4417" not in str(calls)
