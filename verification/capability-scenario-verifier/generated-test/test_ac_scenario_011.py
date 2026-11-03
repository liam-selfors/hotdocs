import json

import pytest

import capability_scenario_verifier


COMPONENT_MD = """---
id: comp-foo
title: Foo Component
status: draft
owners: [lselfors@gmail.com]
realizes: [P-X]
sealed: false
---

# Foo Component
"""

CAPABILITY_MD = """---
id: P-X
title: Foo Capability
status: draft
owners: [lselfors@gmail.com]
---

# Foo Capability

### CS-X-001

Covers: P-X
Kind: llm-judge

```gherkin
Given a widget MARKER_GHERKIN exists
When it is examined
Then it behaves correctly
```
"""

FOO_SOURCE = """# MARKER_SOURCE
def foo():
    return True
"""


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class _Sentinel:
    pass


def _write_fake_llm_endpoint(repo_root, calls_log, response_text, response_error):
    gen_dir = repo_root / "gen" / "llm-endpoint"
    gen_dir.mkdir(parents=True, exist_ok=True)
    module_source = (
        "import json\n"
        "\n"
        f"_CALLS_LOG = {str(calls_log)!r}\n"
        f"_RESPONSE_TEXT = {response_text!r}\n"
        f"_RESPONSE_ERROR = {response_error!r}\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    record = {\"prompt\": prompt, \"model\": model, \"backend_id\": id(backend)}\n"
        "    with open(_CALLS_LOG, \"a\") as f:\n"
        "        f.write(json.dumps(record) + \"\\n\")\n"
        "    return {\n"
        "        \"text\": _RESPONSE_TEXT,\n"
        "        \"model\": model,\n"
        "        \"backend\": backend,\n"
        "        \"model_call_error\": _RESPONSE_ERROR,\n"
        "    }\n"
    )
    (gen_dir / "llm_endpoint.py").write_text(module_source)


def _build_repo(tmp_path, calls_log, response_text, response_error):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    component_dir = repo_root / "specs" / "components" / "foo"
    component_dir.mkdir(parents=True)
    (component_dir / "component.md").write_text(COMPONENT_MD)

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / "foo.md").write_text(CAPABILITY_MD)

    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "foo.py").write_text(FOO_SOURCE)

    _write_fake_llm_endpoint(repo_root, calls_log, response_text, response_error)

    return repo_root


def test_run_capability_gates_dispatches_judge_and_returns_pass(tmp_path):
    sentinel_backend = _Sentinel()
    calls_log = tmp_path / "calls.jsonl"

    response_text = "```json\n" + json.dumps({"result": "pass", "rationale": "ok"}) + "\n```"
    repo_root = _build_repo(tmp_path, calls_log, response_text, None)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=sentinel_backend
    )

    assert calls_log.exists()
    lines = calls_log.read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["model"] == "m"
    assert record["backend_id"] == id(sentinel_backend)
    assert "MARKER_SOURCE" in record["prompt"]
    assert "MARKER_GHERKIN" in record["prompt"]

    report = _get(result, "capability_scenario_report")
    px_report = _get(report, "P-X")
    scenarios = _get(px_report, "scenarios")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert _get(scenario, "id") == "CS-X-001"
    assert _get(scenario, "result") == "pass"
    assert _get(scenario, "rationale") == "ok"


@pytest.mark.parametrize(
    "response_text,response_error",
    [
        (None, {"category": "network", "message": "boom"}),
        ("not json", None),
        (json.dumps({"result": "maybe"}), None),
    ],
    ids=["model_call_error", "unparseable_text", "invalid_result"],
)
def test_run_capability_gates_judge_failure_modes_yield_fail(
    tmp_path, response_text, response_error
):
    sentinel_backend = _Sentinel()
    calls_log = tmp_path / "calls.jsonl"
    repo_root = _build_repo(tmp_path, calls_log, response_text, response_error)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=sentinel_backend
    )

    report = _get(result, "capability_scenario_report")
    px_report = _get(report, "P-X")
    scenarios = _get(px_report, "scenarios")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert _get(scenario, "result") == "fail"
    rationale = _get(scenario, "rationale")
    assert rationale.startswith("judge unavailable")