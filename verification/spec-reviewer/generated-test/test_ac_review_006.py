import json

import pytest

import spec_reviewer


def _make_backend(log_path, reply_text=None, error=None):
    """A mock llm_backend(prompt, model, **params) that logs each call to a file."""

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        if error is not None:
            return {
                "text": None,
                "model": model,
                "backend": "mock",
                "model_call_error": error,
            }
        return {
            "text": reply_text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _read_calls(log_path):
    if not log_path.exists():
        return []
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_judge_parses_reply_and_makes_one_call(tmp_path, monkeypatch):
    # complete() writes its call log under the current directory.
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "backend_calls.jsonl"
    backend = _make_backend(
        log_path, reply_text='ok {"conflicts": true, "rationale": "narrower"}'
    )

    judge = spec_reviewer.glossary_judge("mock", backend)
    assert callable(judge)

    result = judge("Foo", "local meaning", "glossary meaning")

    assert result is not None
    result = tuple(result)
    assert result == (True, "narrower")
    assert result[0] is True
    assert isinstance(result[1], str)

    calls = _read_calls(log_path)
    assert len(calls) == 1
    prompt = calls[0]["prompt"]
    assert isinstance(prompt, str)
    assert "Foo" in prompt
    assert "local meaning" in prompt
    assert "glossary meaning" in prompt


@pytest.mark.parametrize(
    "reply_text,error",
    [
        ("no json", None),
        ('{"conflicts": "yes", "rationale": "r"}', None),
        (None, {"category": "timeout", "message": "timed out"}),
    ],
    ids=["no-json", "non-bool-conflicts", "model-call-error-timeout"],
)
def test_judge_returns_none_for_unusable_reply(tmp_path, monkeypatch, reply_text, error):
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "backend_calls.jsonl"
    backend = _make_backend(log_path, reply_text=reply_text, error=error)

    judge = spec_reviewer.glossary_judge("mock", backend)
    result = judge("Foo", "local meaning", "glossary meaning")

    assert result is None