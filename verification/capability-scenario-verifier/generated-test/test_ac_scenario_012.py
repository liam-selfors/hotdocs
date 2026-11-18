# hotdocs-criterion: sha256:26e807c2e5749c59a3686a059507aff37d3d5b84f715e6280625a2900fc92db4
import json
import shutil
from pathlib import Path

import capability_scenario_verifier


CAP_ID = "P-X"
SCENARIO_ID = "CS-X-001"
GENERATED_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
FAILING_CONTENT = "def test_x():\n    assert False\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _live_repo_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for p in here.parents:
        if p.name == "gen":
            return p.parent
    return None


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_fixture(repo_root, log_path):
    # Product capability with exactly one scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When the widget runs\n"
        "Then the widget works\n"
        "```\n",
    )

    # A realizing, non-sealed component with its code under gen/.
    _write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Widget\n",
    )
    _write(repo_root / "gen" / "widget" / "widget.py", "def hello():\n    return 1\n")

    # Fake test-author: always authors a failing test.
    result_literal = (
        "{"
        + "'component_id': 'comp-widget', "
        + "'criterion_id': bundle['criterion_id'], "
        + "'model': model, "
        + "'seed': seed, "
        + "'prompt_version': 'v1', "
        + "'cache_hit': False, "
        + "'file': {'path': " + repr(GENERATED_PATH) + ", 'content': " + repr(FAILING_CONTENT) + "}, "
        + "'model_call_error': None"
        + "}"
    )
    fake_author = (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('author_test\\n')\n"
        "    return " + result_literal + "\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", fake_author)

    # Fake llm-endpoint.
    fake_llm = (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {'text': 'fail', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", fake_llm)

    # Real compiler copied from the live repository.
    live = _live_repo_root()
    if live is not None:
        src = live / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [l for l in log_path.read_text().splitlines() if l.strip()]


def test_recorded_failure_is_a_hit_and_not_rerun(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fixture(repo_root, log_path)

    # --- Fresh run: the only scenario fails.
    first = capability_scenario_verifier.run_capability_gates(
        CAP_ID, repo_root, model="fake-model", seed=0, llm_backend=None
    )
    assert field(first, "hit") is False
    first_report = field(first, "capability_scenario_report")
    assert first_report is not None
    assert CAP_ID in first_report
    assert field(first_report[CAP_ID], "overall") == "fail"

    record_path = repo_root / "verification" / "capabilities" / CAP_ID / ".provenance.json"
    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert isinstance(record, dict)
    assert record["capability_scenario_report"] == json.loads(json.dumps(first_report))
    assert record["capability_scenario_report"][CAP_ID]["overall"] == "fail"

    calls_after_first = len(_log_lines(log_path))

    # --- Unchanged code: provenance check is a hit carrying the failing report.
    checked = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(checked, "hit") is True
    checked_report = field(checked, "capability_scenario_report")
    assert checked_report is not None
    assert field(checked_report[CAP_ID], "overall") == "fail"

    # --- run_capability_gates with model None returns the hit unchanged.
    second = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, model=None)
    assert field(second, "hit") is True
    second_report = field(second, "capability_scenario_report")
    assert second_report is not None
    assert field(second_report[CAP_ID], "overall") == "fail"

    # No fake module was called during the check or the second gates run.
    assert len(_log_lines(log_path)) == calls_after_first