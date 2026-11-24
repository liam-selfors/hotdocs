# hotdocs-criterion: sha256:e33db11d5cfd6dc296463f59f4435a9430617d8a6342ba7ab56d1a431768aa71
import json
from pathlib import Path

import capability_scenario_verifier


CAPABILITY_ID = "P-X"
SCENARIO_ID = "CS-X-001"
EXPECTED_BUNDLE_KEYS = {"capability_id", "scenario_id", "covers", "kind", "gherkin", "file"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root):
    # A realizing component, unsealed, with code under gen/<slug>/.
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
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "def hello():\n    return 1\n")

    # The capability, with one generated-test scenario.
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
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo is ready\n"
        "When the foo runs\n"
        "Then the foo succeeds\n"
        "```\n",
    )

    # Small fake dependency modules, flat-module shape.
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        'component_id': None,\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': " + repr("verification/capabilities/P-X/generated-test/test_cs_x_001.py") + ",\n"
        "            'content': " + repr("def test_x():\n    assert True\n") + ",\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )


def _make_test_author(log_path):
    def test_author(bundle):
        keys = sorted(str(k) for k in bundle.keys())
        record = {"keys": keys, "scenario_id": str(bundle.get("scenario_id"))}
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    return test_author


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _scenario_result(report, scenario_id):
    entry = field(report, CAPABILITY_ID) if not isinstance(report, dict) else report[CAPABILITY_ID]
    scenarios = field(entry, "scenarios")
    for scenario in scenarios:
        if field(scenario, "id") == scenario_id:
            return field(scenario, "result")
    raise AssertionError("scenario " + repr(scenario_id) + " not in report")


def test_generated_test_scenario_dispatched_on_every_call(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "author_calls.log"
    test_author = _make_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    first_calls = _read_log(log_path)
    assert len(first_calls) >= 1, "test_author not invoked on the first call"

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    second_calls = _read_log(log_path)
    assert len(second_calls) > len(first_calls), (
        "test_author not invoked on the second call; dispatch was short-circuited"
    )
    assert any(c["scenario_id"] == SCENARIO_ID for c in second_calls[len(first_calls):])


def test_bundle_has_exactly_the_scenario_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "author_calls.log"
    test_author = _make_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    calls = _read_log(log_path)
    assert calls, "test_author was never invoked"
    for call in calls:
        assert set(call["keys"]) == EXPECTED_BUNDLE_KEYS
    assert any(c["scenario_id"] == SCENARIO_ID for c in calls)


def test_no_test_author_makes_generated_test_scenario_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo_root)

    assert _scenario_result(report, SCENARIO_ID) == "fail"