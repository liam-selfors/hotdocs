# hotdocs-criterion: sha256:4a73d9fe9aa2ada4ef2e174defe98a70e2b9bfc1484c46217555e2e6e8774c8a
import json
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Sentinel:
    def __repr__(self):
        return "<sentinel-backend>"


FENCED_REPLY = (
    "Verdict:\n```json\n"
    + json.dumps({"result": "pass", "rationale": "ok"})
    + "\n```\nDone."
)
BARE_REPLY = json.dumps({"result": "pass", "rationale": "ok"})


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root, log_path, reply_text, error):
    # Planted python adapter.
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, "
        "\"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # Realizing component.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "# MARKER_SOURCE\n"
        "def foo():\n"
        "    return 'MARKER_SOURCE'\n",
    )

    # Capability with one llm-judge scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [team-a]\n"
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
        "Given MARKER_GHERKIN is present in the system\n"
        "When the capability is exercised\n"
        "Then it behaves as described\n"
        "```\n",
    )

    # Fake llm-endpoint.
    if error:
        ret = (
            "    return {\"text\": None, \"model\": model, \"backend\": \"fake\",\n"
            "            \"model_call_error\": {\"category\": \"network\", "
            "\"message\": \"backend down\"}}\n"
        )
    else:
        ret = (
            "    return {\"text\": " + repr(reply_text) + ", \"model\": model,\n"
            "            \"backend\": \"fake\", \"model_call_error\": None}\n"
        )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "import json\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write(json.dumps({'prompt': prompt, 'model': model,\n"
        "                             'backend_id': id(backend),\n"
        "                             'backend_repr': repr(backend)}) + '\\n')\n"
        + ret,
    )

    # Fake test-author (not expected to be used for an llm-judge scenario).
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\"component_id\": \"comp-foo\",\n"
        "            \"criterion_id\": bundle[\"criterion_id\"],\n"
        "            \"model\": model, \"seed\": seed, \"prompt_version\": \"v1\",\n"
        "            \"cache_hit\": False,\n"
        "            \"file\": {\"path\": \"verification/capabilities/P-X/generated-test/test_cs_x_001.py\",\n"
        "                     \"content\": \"def test_x():\\n    assert True\\n\"},\n"
        "            \"model_call_error\": None, \"repair_attempts\": 0,\n"
        "            \"probe_findings\": []}\n",
    )


def _run(tmp_path, reply_text, error=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "complete_calls.log"
    _build_repo(repo_root, log_path, reply_text, error)
    sentinel = _Sentinel()
    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=sentinel
    )
    calls = []
    if log_path.exists():
        calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    report = field(result, "capability_scenario_report")
    entry = report["P-X"] if isinstance(report, dict) else getattr(report, "P-X")
    scenarios = field(entry, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    return sentinel, calls, matching[0]


def test_fenced_reply_passes_and_complete_called_once_with_prompt(tmp_path):
    sentinel, calls, scenario = _run(tmp_path, FENCED_REPLY)
    assert len(calls) == 1, calls
    call = calls[0]
    assert call["model"] == "m"
    assert call["backend_id"] == id(sentinel)
    assert call["backend_repr"] == "<sentinel-backend>"
    assert "MARKER_SOURCE" in call["prompt"]
    assert "MARKER_GHERKIN" in call["prompt"]
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


def test_unfenced_json_reply_passes(tmp_path):
    sentinel, calls, scenario = _run(tmp_path, BARE_REPLY)
    assert len(calls) == 1, calls
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


@pytest.mark.parametrize(
    "reply_text,error",
    [
        (None, True),
        ("not json", False),
        (json.dumps({"result": "maybe"}), False),
    ],
    ids=["model_call_error", "not_json", "result_maybe"],
)
def test_unusable_reply_fails_with_judge_unavailable(tmp_path, reply_text, error):
    sentinel, calls, scenario = _run(tmp_path, reply_text, error=error)
    assert len(calls) == 1, calls
    assert field(scenario, "result") == "fail"
    rationale = field(scenario, "rationale")
    assert isinstance(rationale, str)
    assert rationale.startswith("judge unavailable"), rationale