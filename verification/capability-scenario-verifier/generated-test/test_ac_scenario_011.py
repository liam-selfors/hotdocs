# hotdocs-criterion: sha256:5b1c02aaf983664e83031f4f6856131e47c75f5443714921ab593f2159103c04
import json
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _SentinelBackend:
    def __call__(self, prompt, model, **params):
        return {
            "text": None,
            "model": model,
            "backend": "sentinel",
            "model_call_error": {"category": "network", "message": "sentinel called"},
        }

    def __repr__(self):
        return "SENTINEL_BACKEND_ac_scenario_011"


SENTINEL = _SentinelBackend()
SENTINEL_REPR = repr(SENTINEL)

FENCED_TEXT = (
    "Verdict:\n```json\n"
    + json.dumps({"result": "pass", "rationale": "ok"})
    + "\n```\nDone."
)
BARE_TEXT = json.dumps({"result": "pass", "rationale": "ok"})


def _ok(text):
    return {"text": text, "model": "m", "backend": "fake", "model_call_error": None}


ERROR_RESPONSE = {
    "text": None,
    "model": "m",
    "backend": "fake",
    "model_call_error": {"category": "network", "message": "endpoint down"},
}


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_repo(root, response, log_path):
    _write(
        root / "specs" / "components" / "foo" / "component.md",
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
        "A fixture component.\n",
    )
    _write(
        root / "gen" / "foo" / "foo.py",
        "# MARKER_SOURCE\n"
        "def foo():\n"
        "    return 'MARKER_SOURCE'\n",
    )
    _write(
        root / "specs" / "product" / "x.md",
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
        "Given a foo holding MARKER_GHERKIN\n"
        "When the foo runs\n"
        "Then the foo succeeds\n"
        "```\n",
    )
    fake_src = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "RESPONSE = " + repr(response) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'prompt': prompt, 'model': model, "
        "'backend': repr(backend)}) + '\\n')\n"
        "    out = dict(RESPONSE)\n"
        "    out['model'] = model\n"
        "    return out\n"
    )
    _write(root / "gen" / "llm-endpoint" / "llm_endpoint.py", fake_src)


def _run(tmp_path, response):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "complete_calls.log"
    _build_repo(repo_root, response, log_path)
    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=SENTINEL
    )
    report = field(result, "capability_scenario_report")
    entry = report["P-X"] if isinstance(report, dict) else getattr(report, "P-X")
    scenarios = field(entry, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    calls = []
    if log_path.exists():
        calls = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return matching[0], calls


def test_fenced_reply_passes_and_complete_called_once(tmp_path):
    scenario, calls = _run(tmp_path, _ok(FENCED_TEXT))
    assert len(calls) == 1, calls
    call = calls[0]
    assert call["model"] == "m"
    assert call["backend"] == SENTINEL_REPR
    assert "MARKER_SOURCE" in call["prompt"]
    assert "MARKER_GHERKIN" in call["prompt"]
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


def test_unfenced_reply_passes(tmp_path):
    scenario, calls = _run(tmp_path, _ok(BARE_TEXT))
    assert len(calls) == 1, calls
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


@pytest.mark.parametrize(
    "response",
    [
        ERROR_RESPONSE,
        _ok("not json"),
        _ok(json.dumps({"result": "maybe"})),
    ],
    ids=["model_call_error", "not_json", "result_maybe"],
)
def test_bad_reply_fails_as_judge_unavailable(tmp_path, response):
    scenario, calls = _run(tmp_path, response)
    assert len(calls) == 1, calls
    assert field(scenario, "result") == "fail"
    rationale = field(scenario, "rationale")
    assert isinstance(rationale, str)
    assert rationale.startswith("judge unavailable"), rationale