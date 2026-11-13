"""AC-SCENARIO-004 (Covers: R-SCENARIO-003).

- A generated-test scenario is dispatched fresh to the injected
  test_author on every run_capability_scenarios call, with no cache-file
  short-circuit.
- The bundle given to the injected test_author has exactly the keys
  capability_id, scenario_id, covers, kind, gherkin, file.
- With no test_author supplied, a generated-test scenario's result is
  "fail".
"""

import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

import capability_scenario_verifier


CAPABILITY_ID = "P-X"
SCENARIO_ID = "CS-X-001"
GENERATED_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
GENERATED_CONTENT = "def test_x():\n    assert True\n"


def field(value, name):
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def capability_entry(report, capability_id):
    if isinstance(report, Mapping):
        return report[capability_id]
    if hasattr(report, "__getitem__"):
        return report[capability_id]
    return getattr(report, capability_id)


def scenario_result(report, capability_id, scenario_id):
    entry = capability_entry(report, capability_id)
    scenarios = field(entry, "scenarios")
    for scenario in scenarios:
        if field(scenario, "id") == scenario_id:
            return field(scenario, "result")
    raise AssertionError(
        f"scenario {scenario_id} not found in report for {capability_id}: {report!r}"
    )


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


FAKE_TEST_AUTHOR_MODULE = '''\
def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    criterion_id = bundle["criterion_id"]
    name = "test_" + str(criterion_id).lower().replace("-", "_") + ".py"
    return {
        "component_id": bundle.get("component_id", ""),
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/" + name,
            "content": "def test_x():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''

FAKE_LLM_ENDPOINT_MODULE = '''\
def complete(prompt, model, *, backend=None, **params):
    return {
        "text": "pass",
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }
'''


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(root: Path) -> Path:
    comp = root / "specs" / "components" / "widget"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n\n"
        "# Widget\n\n"
        "A small widget component used as a fixture.\n",
    )
    _write(
        comp / "requirements" / "R-WIDGET-001.md",
        "**R-WIDGET-001** — The widget MUST exist.\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nwidget_value() -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        root / "gen" / "widget" / "widget.py",
        "def widget_value():\n    return 1\n",
    )

    _write(
        root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n\n"
        "# P-X\n\n"
        "A capability realized by the widget.\n\n"
        "### CS-X-001\n\n"
        "Covers: P-X\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When the widget is used\n"
        "Then the widget works\n"
        "```\n",
    )

    _write(root / "gen" / "test-author" / "test_author.py", FAKE_TEST_AUTHOR_MODULE)
    _write(root / "gen" / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT_MODULE)

    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
    return root


def _make_recording_test_author(log_path: Path):
    def fake_test_author(bundle):
        keys = sorted(bundle.keys()) if isinstance(bundle, Mapping) else None
        record = {
            "keys": keys,
            "bundle": dict(bundle) if isinstance(bundle, Mapping) else repr(bundle),
        }
        with open(log_path, "a") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        return {
            "model_call_error": None,
            "file": {"path": GENERATED_PATH, "content": GENERATED_CONTENT},
        }

    return fake_test_author


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _build_repo(root)
    monkeypatch.chdir(tmp_path)
    return root


def test_generated_test_scenario_dispatched_fresh_on_every_call(repo, tmp_path):
    log_path = tmp_path / "test_author_calls.jsonl"
    fake = _make_recording_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget"], repo, test_author=fake
    )
    first_calls = _read_log(log_path)
    assert len(first_calls) >= 1, "test_author was not invoked on the first call"

    # Content unchanged; any file the first run wrote stays in place.
    capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget"], repo, test_author=fake
    )
    second_calls = _read_log(log_path)
    assert len(second_calls) > len(first_calls), (
        "test_author was not invoked on the second call: a cache file "
        "short-circuited the dispatch"
    )


def test_bundle_keys_are_exactly_the_scenario_shape(repo, tmp_path):
    log_path = tmp_path / "test_author_bundles.jsonl"
    fake = _make_recording_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget"], repo, test_author=fake
    )
    records = _read_log(log_path)
    assert records, "test_author was never invoked"
    expected = sorted(
        ["capability_id", "scenario_id", "covers", "kind", "gherkin", "file"]
    )
    for record in records:
        assert record["keys"] == expected, (
            f"bundle keys {record['keys']!r} != {expected!r}"
        )
    bundle = records[0]["bundle"]
    assert bundle["capability_id"] == CAPABILITY_ID
    assert bundle["scenario_id"] == SCENARIO_ID


def test_generated_test_scenario_fails_without_test_author(repo):
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget"], repo
    )
    assert scenario_result(report, CAPABILITY_ID, SCENARIO_ID) == "fail"