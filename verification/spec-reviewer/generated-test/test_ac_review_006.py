# hotdocs-criterion: sha256:52dd2933f0a4e8cc603916eff959e281e70c0c26b553bf8e030f1e59418c5783
import spec_reviewer


def make_backend(text=None, error=None):
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
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend, calls


def test_judge_parses_reply_and_makes_one_call_with_all_inputs():
    backend, calls = make_backend(
        text='ok {"conflicts": true, "rationale": "narrower"}'
    )
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


def test_judge_returns_none_for_reply_without_json():
    backend, calls = make_backend(text="no json")
    judge = spec_reviewer.glossary_judge("mock", backend)
    assert judge("Foo", "local meaning", "glossary meaning") is None
    assert len(calls) == 1


def test_judge_returns_none_for_non_bool_conflicts():
    backend, calls = make_backend(text='{"conflicts": "yes", "rationale": "r"}')
    judge = spec_reviewer.glossary_judge("mock", backend)
    assert judge("Foo", "local meaning", "glossary meaning") is None
    assert len(calls) == 1


def test_judge_returns_none_for_model_call_error():
    backend, calls = make_backend(
        error={"category": "timeout", "message": "timeout"}
    )
    judge = spec_reviewer.glossary_judge("mock", backend)
    assert judge("Foo", "local meaning", "glossary meaning") is None
    assert len(calls) == 1