# hotdocs-criterion: sha256:39417c6c89ab90006148579eff477d5b46f879ef1fa8b41d89e7ad5ab1f1cb4e
import json
from pathlib import Path

import capability_scenario_verifier


SCENARIO_ID = "CS-X-001"
CAPABILITY_ID = "P-X"
COMPONENT_ID = "comp-foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    repo_root = Path(repo_root)
    # A non-sealed component realizing P-X, code under gen/foo/.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "realizes: [P-X]\n"
        + "sealed: false\n"
        + "---\n"
        + "\n"
        + "# Foo\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "def foo():\n    return 1\n",
    )
    # The capability with one generated-test scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        + "id: P-X\n"
        + "title: X\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# X\n"
        + "\n"
        + "### CS-X-001\n"
        + "\n"
        + "Covers: P-X\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given a value is 1\n"
        + "When nothing happens\n"
        + "Then the value equals 1\n"
        + "```\n",
    )
    # Fake dependencies at the documented paths (flat module shape).
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        + "    return {\n"
        + "        'component_id': '',\n"
        + "        'criterion_id': bundle['criterion_id'],\n"
        + "        'model': model,\n"
        + "        'seed': seed,\n"
        + "        'prompt_version': 'v1',\n"
        + "        'cache_hit': False,\n"
        + "        'file': {\n"
        + "            'path': " + repr("verification/capabilities/P-X/generated-test/test_cs_x_001.py") + ",\n"
        + "            'content': " + repr("def test_x():\n    assert True\n") + ",\n"
        + "        },\n"
        + "        'model_call_error': None,\n"
        + "    }\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        + "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )
    return repo_root


def _make_test_author(log_path):
    log_path = Path(log_path)

    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(sorted(list(bundle.keys()))) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    return test_author


def _log_lines(log_path):
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _scenario_result(report, scenario_id):
    entry = field(report, CAPABILITY_ID)
    scenarios = field(entry, "scenarios")
    for scenario in scenarios:
        if field(scenario, "id") == scenario_id:
            return field(scenario, "result")
    raise AssertionError("scenario " + repr(scenario_id) + " not found in report")


def test_generated_test_dispatched_fresh_on_both_calls(tmp_path):
    repo_root = _build_fixture(tmp_path / "repo")
    log_path = tmp_path / "author_calls.log"
    test_author = _make_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, test_author=test_author
    )
    assert len(_log_lines(log_path)) == 1

    capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, test_author=test_author
    )
    assert len(_log_lines(log_path)) == 2


def test_bundle_keys_are_exactly_the_scenario_shape(tmp_path):
    repo_root = _build_fixture(tmp_path / "repo")
    log_path = tmp_path / "author_calls.log"
    test_author = _make_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, test_author=test_author
    )

    lines = _log_lines(log_path)
    assert len(lines) >= 1
    expected = sorted(["capability_id", "scenario_id", "covers", "kind", "gherkin", "file"])
    for line in lines:
        assert json.loads(line) == expected


def test_generated_test_without_test_author_fails(tmp_path):
    repo_root = _build_fixture(tmp_path / "repo")

    report = capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root
    )

    assert _scenario_result(report, SCENARIO_ID) == "fail"