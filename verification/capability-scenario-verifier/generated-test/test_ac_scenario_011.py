# hotdocs-criterion: sha256:e8ac1ff71127e6c11cdde676b34599414cdda4a7aa661965cd810833926a4330
import json
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _SentinelBackend:
    def __repr__(self):
        return "SENTINEL_BACKEND_7731"

    def __call__(self, prompt, model, **params):
        raise AssertionError("sentinel backend must never be invoked directly")


SENTINEL = _SentinelBackend()

KIND_PYTHON_SOURCE = (
    "import sys\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": sys.executable}\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "realizes: [P-X]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "A fixture component realizing P-X.\n"
)

FOO_SOURCE = (
    "# MARKER_SOURCE\n"
    "def foo():\n"
    "    return 'MARKER_SOURCE'\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-X\n"
    "title: Capability X\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "---\n"
    "\n"
    "# Capability X\n"
    "\n"
    "### CS-X-001\n"
    "\n"
    "Covers: P-X\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the code contains MARKER_GHERKIN behavior\n"
    "When the judge reads it\n"
    "Then the behavior is present\n"
    "```\n"
)


def _fake_llm_source(log_path, reply):
    return (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPLY = " + repr(reply) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'prompt': prompt, 'model': model,"
        " 'backend': repr(backend)}) + '\\n')\n"
        "    out = dict(REPLY)\n"
        "    out['model'] = model\n"
        "    return out\n"
    )


def _build_repo(repo_root, reply):
    (repo_root / "gen" / "kind-python").mkdir(parents=True)
    (repo_root / "gen" / "kind-python" / "kind_python.py").write_text(KIND_PYTHON_SOURCE)

    (repo_root / "specs" / "components" / "foo").mkdir(parents=True)
    (repo_root / "specs" / "components" / "foo" / "component.md").write_text(COMPONENT_MD)
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "foo.py").write_text(FOO_SOURCE)

    (repo_root / "specs" / "product").mkdir(parents=True)
    (repo_root / "specs" / "product" / "x.md").write_text(PRODUCT_MD)

    log_path = repo_root / "llm_calls.log"
    (repo_root / "gen" / "llm-endpoint").mkdir(parents=True)
    (repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(
        _fake_llm_source(log_path, reply)
    )
    return log_path


def _text_reply(text):
    return {"text": text, "model": "m", "backend": "fake", "model_call_error": None}


def _scenario(result):
    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    cap = report["P-X"] if isinstance(report, dict) else getattr(report, "P-X")
    scenarios = field(cap, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matches) == 1
    return matches[0]


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_fenced_reply_single_call_with_prompt_and_pass(tmp_path):
    text = (
        "Verdict:\n```json\n"
        + json.dumps({"result": "pass", "rationale": "ok"})
        + "\n```\nDone."
    )
    log_path = _build_repo(tmp_path, _text_reply(text))

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", tmp_path, "m", llm_backend=SENTINEL
    )

    calls = _read_log(log_path)
    assert len(calls) == 1
    call = calls[0]
    assert call["model"] == "m"
    assert call["backend"] == "SENTINEL_BACKEND_7731"
    assert "MARKER_SOURCE" in call["prompt"]
    assert "MARKER_GHERKIN" in call["prompt"]

    scenario = _scenario(result)
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


def test_unfenced_json_reply_passes(tmp_path):
    text = json.dumps({"result": "pass", "rationale": "ok"})
    _build_repo(tmp_path, _text_reply(text))

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", tmp_path, "m", llm_backend=SENTINEL
    )

    scenario = _scenario(result)
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


@pytest.mark.parametrize(
    "reply",
    [
        {
            "text": None,
            "model": "m",
            "backend": "fake",
            "model_call_error": {"category": "network", "message": "backend unreachable"},
        },
        {"text": "not json", "model": "m", "backend": "fake", "model_call_error": None},
        {
            "text": json.dumps({"result": "maybe"}),
            "model": "m",
            "backend": "fake",
            "model_call_error": None,
        },
    ],
    ids=["model_call_error", "not_json", "result_maybe"],
)
def test_bad_reply_fails_judge_unavailable(tmp_path, reply):
    _build_repo(tmp_path, reply)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", tmp_path, "m", llm_backend=SENTINEL
    )

    scenario = _scenario(result)
    assert field(scenario, "result") == "fail"
    rationale = field(scenario, "rationale")
    assert isinstance(rationale, str)
    assert rationale.startswith("judge unavailable")