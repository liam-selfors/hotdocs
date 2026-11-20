# hotdocs-criterion: sha256:8b5a4f85fa35ae5504b835d80eac5fa9158a8ce34b56bc17e4abf40d4b8b0543
import spec_reviewer

import pytest


def make_backend(reply_text=None, error=None):
    calls = []

    def backend(prompt, model, **params):
        calls.append({"prompt": prompt, "model": model, "params": params})
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

    return backend, calls


def test_judge_parses_reply_and_calls_backend_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend, calls = make_backend('ok {"conflicts": true, "rationale": "narrower"}')
    judge = spec_reviewer.glossary_judge("mock", backend)
    assert callable(judge)

    result = judge("Foo", "local meaning", "glossary meaning")

    assert result is not None
    assert tuple(result) == (True, "narrower")
    assert result[0] is True
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
        (None, {"category": "timeout", "message": "the call timed out"}),
    ],
    ids=["no-json", "non-bool-conflicts", "model-call-error-timeout"],
)
def test_judge_returns_none_for_bad_replies(tmp_path, monkeypatch, reply_text, error):
    monkeypatch.chdir(tmp_path)
    backend, calls = make_backend(reply_text, error)
    judge = spec_reviewer.glossary_judge("mock", backend)

    result = judge("Foo", "local meaning", "glossary meaning")

    assert result is None
    assert len(calls) == 1