# hotdocs-criterion: sha256:5afda32c4ff5158693e493518ef03d39ff85488bb36807a47b535c5488063db5
import spec_reviewer


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


def test_glossary_judge_parses_reply_and_makes_one_call(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend, calls = make_backend('ok {"conflicts": true, "rationale": "narrower"}')
    judge = spec_reviewer.glossary_judge("mock", backend)
    assert callable(judge)

    result = judge("Foo", "local meaning", "glossary meaning")

    assert result is not None
    assert tuple(result) == (True, "narrower")
    assert len(calls) == 1
    prompt = calls[0]["prompt"]
    assert isinstance(prompt, str)
    assert "Foo" in prompt
    assert "local meaning" in prompt
    assert "glossary meaning" in prompt


def test_glossary_judge_returns_none_for_no_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend, calls = make_backend("no json")
    judge = spec_reviewer.glossary_judge("mock", backend)
    assert judge("Foo", "local meaning", "glossary meaning") is None
    assert len(calls) == 1


def test_glossary_judge_returns_none_for_non_bool_conflicts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend, calls = make_backend('{"conflicts": "yes", "rationale": "r"}')
    judge = spec_reviewer.glossary_judge("mock", backend)
    assert judge("Foo", "local meaning", "glossary meaning") is None
    assert len(calls) == 1


def test_glossary_judge_returns_none_for_model_call_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend, calls = make_backend(
        error={"category": "timeout", "message": "request timed out"}
    )
    judge = spec_reviewer.glossary_judge("mock", backend)
    assert judge("Foo", "local meaning", "glossary meaning") is None
    assert len(calls) == 1