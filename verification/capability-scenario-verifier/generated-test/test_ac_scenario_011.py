import json
import textwrap

import pytest

import capability_scenario_verifier


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


FOO_COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [qa]
realizes: [P-X]
sealed: false
---

# Foo

A fixture component realizing P-X.
"""

CAPABILITY_X_MD = """---
id: P-X
title: Capability X
status: draft
owners: [qa]
---

# Capability X

### CS-X-001

Covers: P-X
Kind: llm-judge

```gherkin
Given MARKER_GHERKIN is present in the scenario
When the capability gate runs
Then the scenario is judged
```
"""

FOO_SOURCE = """# MARKER_SOURCE
def foo():
    pass
"""

SENTINEL_BACKEND = "sentinel-backend-7e862b1d"


def _llm_endpoint_source(record_path, response_text, response_error):
    return textwrap.dedent(
        """
        import json

        def complete(prompt, model, backend=None, **params):
            with open({record_path!r}, "a") as f:
                f.write(json.dumps({{"prompt": prompt, "model": model, "backend": backend}}) + "\\n")
            return {{"text": {response_text!r}, "model_call_error": {response_error!r}}}
        """
    ).format(
        record_path=str(record_path),
        response_text=response_text,
        response_error=response_error,
    )


def _build_repo(repo_root, record_path, response_text, response_error):
    component_dir = repo_root / "specs" / "components" / "foo"
    component_dir.mkdir(parents=True)
    (component_dir / "component.md").write_text(FOO_COMPONENT_MD)

    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / "foo.py").write_text(FOO_SOURCE)

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / "capability-x.md").write_text(CAPABILITY_X_MD)

    endpoint_dir = repo_root / "gen" / "llm-endpoint"
    endpoint_dir.mkdir(parents=True)
    (endpoint_dir / "llm_endpoint.py").write_text(
        _llm_endpoint_source(record_path, response_text, response_error)
    )


def _scenario_for(result, scenario_id="CS-X-001"):
    report = _get(result, "capability_scenario_report")
    px = _get(report, "P-X")
    scenarios = _get(px, "scenarios")
    return next(s for s in scenarios if _get(s, "id") == scenario_id)


def test_llm_judge_scenario_dispatches_once_and_passes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    record_path = tmp_path / "calls.jsonl"
    _build_repo(
        repo_root,
        record_path,
        response_text='```json\n{"result": "pass", "rationale": "ok"}\n```',
        response_error=None,
    )

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=SENTINEL_BACKEND,
    )

    calls = [json.loads(line) for line in record_path.read_text().splitlines()]
    assert len(calls) == 1
    call = calls[0]
    assert call["model"] == "m"
    assert call["backend"] == SENTINEL_BACKEND
    assert "MARKER_SOURCE" in call["prompt"]
    assert "MARKER_GHERKIN" in call["prompt"]

    scenario = _scenario_for(result)
    assert _get(scenario, "result") == "pass"
    assert _get(scenario, "rationale") == "ok"


@pytest.mark.parametrize(
    "response_text,response_error",
    [
        (None, {"category": "rate_limit", "message": "429 from backend"}),
        ("not json", None),
        ('```json\n{"result": "maybe"}\n```', None),
    ],
    ids=["model_call_error", "unparseable_text", "invalid_result_value"],
)
def test_llm_judge_scenario_fails_when_judge_unavailable(
    tmp_path, response_text, response_error
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    record_path = tmp_path / "calls.jsonl"
    _build_repo(repo_root, record_path, response_text, response_error)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=SENTINEL_BACKEND,
    )

    scenario = _scenario_for(result)
    assert _get(scenario, "result") == "fail"
    rationale = _get(scenario, "rationale")
    assert rationale.startswith("judge unavailable")