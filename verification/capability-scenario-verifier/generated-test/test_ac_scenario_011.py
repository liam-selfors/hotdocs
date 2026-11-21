# hotdocs-criterion: sha256:6592f2a9c6bc8d895208ee2bd570704bbe2c17117262d9c0661768fc71b9eb1f
import json
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FENCE = "`" * 3

PASS_PAYLOAD = json.dumps({"result": "pass", "rationale": "ok"})

FENCED_TEXT = "Verdict:\n" + FENCE + "json\n" + PASS_PAYLOAD + "\n" + FENCE + "\nDone."


def _ok_response(text):
    return {"text": text, "model": "m", "backend": "fake", "model_call_error": None}


def _error_response():
    return {
        "text": None,
        "model": "m",
        "backend": "fake",
        "model_call_error": {"category": "network", "message": "connection dropped"},
    }


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_repo(repo_root, log_path, response):
    # python adapter
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # realizing component
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "MARKER = " + repr("MARKER_SOURCE") + "\n"
        "\n"
        "\n"
        "def run():\n"
        "    return MARKER\n",
    )

    # capability with one llm-judge scenario
    _write(
        repo_root / "specs" / "product" / "x.md",
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
        + FENCE + "gherkin\n"
        "Given a foo holding MARKER_GHERKIN\n"
        "When it runs\n"
        "Then it behaves\n"
        + FENCE + "\n",
    )

    # fake llm-endpoint
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "RESPONSE = " + repr(response) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, \"a\") as handle:\n"
        "        handle.write(json.dumps({\"prompt\": prompt, \"model\": model,\n"
        "                                 \"backend_id\": id(backend)}) + \"\\n\")\n"
        "    out = dict(RESPONSE)\n"
        "    out[\"model\"] = model\n"
        "    return out\n",
    )


def _run(tmp_path, name, response):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-calls.log")
    _build_repo(repo_root, log_path, response)
    sentinel = object()
    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=sentinel
    )
    report = field(result, "capability_scenario_report")
    entry = report["P-X"] if isinstance(report, dict) else getattr(report, "P-X")
    scenarios = field(entry, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    calls = []
    if log_path.exists():
        calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    return matching[0], calls, sentinel


def test_fenced_reply_dispatches_once_and_passes(tmp_path):
    scenario, calls, sentinel = _run(tmp_path, "fenced", _ok_response(FENCED_TEXT))

    assert len(calls) == 1, calls
    call = calls[0]
    assert call["model"] == "m"
    assert call["backend_id"] == id(sentinel)
    assert "MARKER_SOURCE" in call["prompt"]
    assert "MARKER_GHERKIN" in call["prompt"]

    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


def test_unfenced_reply_passes(tmp_path):
    scenario, calls, _ = _run(tmp_path, "plain", _ok_response(PASS_PAYLOAD))

    assert len(calls) == 1, calls
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


@pytest.mark.parametrize(
    "name,response",
    [
        ("error", _error_response()),
        ("notjson", _ok_response("not json")),
        ("maybe", _ok_response(json.dumps({"result": "maybe"}))),
    ],
)
def test_unusable_reply_fails_as_judge_unavailable(tmp_path, name, response):
    scenario, calls, _ = _run(tmp_path, name, response)

    assert len(calls) == 1, calls
    assert field(scenario, "result") == "fail"
    rationale = field(scenario, "rationale")
    assert isinstance(rationale, str)
    assert rationale.startswith("judge unavailable"), rationale