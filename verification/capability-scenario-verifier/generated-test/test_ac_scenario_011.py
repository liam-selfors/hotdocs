import json
import os
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


STATE_ENV = "CSV_AC_SCENARIO_011_FAKE_STATE_DIR"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    # Fallback: nearest ancestor holding the sealed compiler.
    for parent in here.parents:
        if (parent / "pipeline" / "criterion-compiler").is_dir():
            return parent
    return None


FAKE_LLM_ENDPOINT = '''\
import json
import os


def complete(prompt, model, *, backend=None, **params):
    state = os.environ["%s"]
    with open(os.path.join(state, "complete_log.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "prompt": prompt,
            "model": model,
            "backend_id": id(backend),
            "backend_repr": repr(backend),
        }) + "\\n")
    with open(os.path.join(state, "reply.json"), encoding="utf-8") as fh:
        reply = json.load(fh)
    reply["model"] = model
    return reply
''' % STATE_ENV


FAKE_TEST_AUTHOR = '''\
import json
import os


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    state = os.environ["%s"]
    with open(os.path.join(state, "author_log.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"criterion_id": bundle["criterion_id"]}) + "\\n")
    return {
        "model_call_error": None,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
            "content": "def test_x():\\n    assert True\\n",
        },
    }
''' % STATE_ENV


COMPONENT_MD = """\
---
id: comp-foo
title: Foo
status: draft
owners: [tester]
realizes: [P-X]
sealed: false
---

# comp-foo

A small component realizing P-X.
"""

PRODUCT_MD = """\
---
id: P-X
title: X capability
status: draft
owners: [tester]
---

# P-X

The X capability.

### CS-X-001

Covers: P-X
Kind: llm-judge

```gherkin
Given MARKER_GHERKIN is present in the system
When the judge reads the realizing code
Then the capability behaves as described
```
"""


class _SentinelBackend:
    def __call__(self, prompt, model, **params):
        return {"text": "unused", "model": model, "backend": "sentinel",
                "model_call_error": None}

    def __repr__(self):
        return "<AC-SCENARIO-011 sentinel backend>"


def _build_repo(tmp_path, monkeypatch, reply):
    repo_root = tmp_path / "repo"
    state = tmp_path / "fake_state"
    state.mkdir(parents=True)
    monkeypatch.setenv(STATE_ENV, str(state))
    (state / "reply.json").write_text(json.dumps(reply), encoding="utf-8")

    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "**R-FOO-001** — foo MUST exist.\n", encoding="utf-8")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it exists\n```\n",
        encoding="utf-8")
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo()\n```\n", encoding="utf-8")

    gen_foo = repo_root / "gen" / "foo"
    gen_foo.mkdir(parents=True)
    (gen_foo / "foo.py").write_text(
        'MARKER = "MARKER_SOURCE"\n\n\ndef foo():\n    return MARKER\n',
        encoding="utf-8")

    product = repo_root / "specs" / "product"
    product.mkdir(parents=True)
    (product / "x.md").write_text(PRODUCT_MD, encoding="utf-8")

    endpoint_dir = repo_root / "gen" / "llm-endpoint"
    endpoint_dir.mkdir(parents=True)
    (endpoint_dir / "llm_endpoint.py").write_text(FAKE_LLM_ENDPOINT, encoding="utf-8")

    author_dir = repo_root / "gen" / "test-author"
    author_dir.mkdir(parents=True)
    (author_dir / "test_author.py").write_text(FAKE_TEST_AUTHOR, encoding="utf-8")

    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src, repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__"))

    return repo_root, state


def _read_log(state):
    path = state / "complete_log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _scenario(result, scenario_id="CS-X-001"):
    report = field(result, "capability_scenario_report")
    assert report is not None
    entry = report["P-X"] if isinstance(report, dict) else getattr(report, "P-X")
    scenarios = field(entry, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == scenario_id]
    assert len(matches) == 1, scenarios
    return matches[0]


def _ok(text):
    return {"text": text, "model": "m", "backend": "fake", "model_call_error": None}


def test_judge_makes_one_call_with_markers_and_parses_fenced_reply(tmp_path, monkeypatch):
    fenced = '```json\n{"result": "pass", "rationale": "ok"}\n```'
    repo_root, state = _build_repo(tmp_path, monkeypatch, _ok(fenced))
    sentinel = _SentinelBackend()

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=sentinel)

    calls = _read_log(state)
    assert len(calls) == 1, calls
    call = calls[0]
    assert call["model"] == "m"
    assert call["backend_id"] == id(sentinel)
    assert call["backend_repr"] == repr(sentinel)
    assert "MARKER_SOURCE" in call["prompt"]
    assert "MARKER_GHERKIN" in call["prompt"]

    scenario = _scenario(result)
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


@pytest.mark.parametrize(
    "reply",
    [
        {"text": None, "model": "m", "backend": "fake",
         "model_call_error": {"category": "network", "message": "network down"}},
        _ok("not json"),
        _ok('{"result": "maybe"}'),
    ],
    ids=["model_call_error", "not_json", "result_maybe"],
)
def test_judge_failure_modes_yield_fail_judge_unavailable(tmp_path, monkeypatch, reply):
    repo_root, state = _build_repo(tmp_path, monkeypatch, reply)
    sentinel = _SentinelBackend()

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=sentinel)

    scenario = _scenario(result)
    assert field(scenario, "result") == "fail"
    rationale = field(scenario, "rationale")
    assert isinstance(rationale, str)
    assert rationale.startswith("judge unavailable"), rationale