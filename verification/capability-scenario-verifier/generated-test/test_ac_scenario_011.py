import json
import textwrap
from pathlib import Path

import pytest

import capability_scenario_verifier

SENTINEL_BACKEND = "SENTINEL-BACKEND-CS-X-001"
PASS_TEXT = "```json\n{\"result\": \"pass\", \"rationale\": \"ok\"}\n```"


def _dual(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_repo(tmp_path: Path, *, error=None, text=None) -> Path:
    repo_root = tmp_path / "repo"

    _write(
        repo_root / "specs" / "product" / "foo.md",
        textwrap.dedent(
            """\
            ---
            id: P-X
            title: Foo Capability
            status: ratified
            owners: [alice]
            last_ratified_commit: 0000000000000000000000000000000000000000
            ---

            # P-X

            A fake product capability used for AC-SCENARIO-011.

            ### CS-X-001

            Covers: P-X
            Kind: llm-judge

            ```gherkin
            Given MARKER_GHERKIN
            When something happens
            Then something else happens
            ```
            """
        ),
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        textwrap.dedent(
            """\
            ---
            id: comp-foo
            title: Foo Component
            status: ratified
            owners: [alice]
            sealed: false
            realizes: [P-X]
            last_ratified_commit: 0000000000000000000000000000000000000000
            ---

            # Foo Component

            A fake realizing component used for AC-SCENARIO-011.
            """
        ),
    )

    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "# MARKER_SOURCE\ndef foo():\n    pass\n",
    )

    response_dict = {"text": text, "model_call_error": error}

    module_src = (
        "import json\n"
        "import os\n"
        "\n"
        "CALL_LOG = os.path.join(os.path.dirname(__file__), \"call_log.jsonl\")\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(CALL_LOG, \"a\") as f:\n"
        "        f.write(json.dumps({\"prompt\": prompt, \"model\": model, \"backend\": backend}) + \"\\n\")\n"
        "    return " + repr(response_dict) + "\n"
    )

    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", module_src)

    return repo_root


def _scenario_result(result, capability_id, scenario_id):
    report = _dual(result, "capability_scenario_report")
    capability_entry = _dual(report, capability_id)
    scenarios = _dual(capability_entry, "scenarios")
    for scenario in scenarios:
        if _dual(scenario, "id") == scenario_id:
            return scenario
    raise AssertionError(
        "scenario %s not found in report for %s" % (scenario_id, capability_id)
    )


def test_llm_judge_pass_dispatches_single_call_and_records_result(tmp_path):
    repo_root = _build_repo(tmp_path, text=PASS_TEXT)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=SENTINEL_BACKEND
    )

    call_log_path = repo_root / "gen" / "llm-endpoint" / "call_log.jsonl"
    lines = call_log_path.read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["model"] == "m"
    assert record["backend"] == SENTINEL_BACKEND
    assert "MARKER_SOURCE" in record["prompt"]
    assert "MARKER_GHERKIN" in record["prompt"]

    scenario = _scenario_result(result, "P-X", "CS-X-001")
    assert _dual(scenario, "result") == "pass"
    assert _dual(scenario, "rationale") == "ok"


@pytest.mark.parametrize(
    "error,text",
    [
        ({"category": "network", "message": "boom"}, None),
        (None, "not json"),
        (None, json.dumps({"result": "maybe"})),
    ],
    ids=["model_call_error", "unparseable_text", "invalid_result_value"],
)
def test_llm_judge_failure_modes_never_pass(tmp_path, error, text):
    repo_root = _build_repo(tmp_path, error=error, text=text)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=SENTINEL_BACKEND
    )

    scenario = _scenario_result(result, "P-X", "CS-X-001")
    assert _dual(scenario, "result") == "fail"
    rationale = _dual(scenario, "rationale")
    assert rationale is not None
    assert rationale.startswith("judge unavailable")