"""Live suite (`D315`): real provider calls, skipped unless HOTDOCS_LIVE=1.

    HOTDOCS_LIVE=1 HOTDOCS_LIVE_MODEL=claude-cli:claude-opus-5-5 \
        pytest verification/llm-endpoint/test_live_providers.py

Never part of a bootstrap, a gate, or `hotdocs verify`.
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-endpoint"))
import llm_endpoint  # noqa: E402

MODEL = os.environ.get("HOTDOCS_LIVE_MODEL", "claude-cli:claude-opus-5-5")
pytestmark = pytest.mark.skipif(os.environ.get("HOTDOCS_LIVE") != "1", reason="live suite: set HOTDOCS_LIVE=1")


def test_one_word_reply():
    reply = llm_endpoint.complete("Reply with exactly the word: pong", MODEL)
    assert reply["model_call_error"] is None, reply["model_call_error"]
    assert "pong" in reply["text"].lower()


def test_long_reply_is_not_cut_off():
    prompt = ("Write the integers from 1 to 400, one per line, then a final line "
              "containing only the word END. No other text.")
    reply = llm_endpoint.complete(prompt, MODEL)
    assert reply["model_call_error"] is None, reply["model_call_error"]
    lines = [line.strip() for line in reply["text"].strip().splitlines() if line.strip()]
    assert lines[-1] == "END"
    assert "400" in lines
