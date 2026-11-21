# hotdocs-criterion: sha256:e811b8fae9631dd62cd3264b77a761b62d0e929811d48808db7e8fb6cb020f8f
import json
import sys
from pathlib import Path

import capability_scenario_verifier


SCENARIO_ID = "CS-X-001"
CAPABILITY_ID = "P-X"
EXPECTED_BUNDLE_KEYS = {"capability_id", "scenario_id", "covers", "kind", "gherkin", "file"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root):
    # Planted python adapter.
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # A component realizing P-X.
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
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "def value():\n"
        "    return 1\n",
    )

    # The capability with one generated-test scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it passes\n"
        "```\n",
    )

    # Fake test-author dependency (real signature and full result shape).
    test_author_result = {
        "component_id": "comp-foo",
        "criterion_id": SCENARIO_ID,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
            "content": "def test_x():\n    assert True\n",
        },
        "model_call_error": None,
        "repair_attempts": 0,
        "probe_findings": [],
    }
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = " + repr("generated_test@3.0.0") + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    result = " + repr(test_author_result) + "\n"
        "    result['model'] = model\n"
        "    result['seed'] = seed\n"
        "    return result\n",
    )

    # Fake llm-endpoint dependency.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {" + repr("text") + ": " + repr("pass") + ", "
        + repr("model") + ": model, "
        + repr("backend") + ": " + repr("fake") + ", "
        + repr("model_call_error") + ": None}\n",
    )


def _make_test_author(log_path):
    def test_author(bundle):
        if isinstance(bundle, dict):
            keys = sorted(str(k) for k in bundle.keys())
            scenario_id = bundle.get("scenario_id")
        else:
            keys = sorted(str(k) for k in vars(bundle).keys())
            scenario_id = getattr(bundle, "scenario_id", None)
        with open(log_path, "a") as fh:
            fh.write(json.dumps({"keys": keys, "scenario_id": str(scenario_id)}) + "\n")
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
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _scenario_entry(report, scenario_id):
    capability = field(report, CAPABILITY_ID)
    scenarios = field(capability, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == scenario_id]
    assert len(matches) == 1, scenarios
    return matches[0]


def test_generated_test_scenario_dispatched_fresh_on_every_call(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "author_calls.log"
    test_author = _make_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    assert len(_read_log(log_path)) == 1

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    calls = _read_log(log_path)
    assert len(calls) == 2, calls
    assert all(c["scenario_id"] == SCENARIO_ID for c in calls)


def test_bundle_keys_are_exactly_the_scenario_shape(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "author_calls.log"
    test_author = _make_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    calls = _read_log(log_path)
    assert len(calls) >= 1, calls
    for call in calls:
        assert set(call["keys"]) == EXPECTED_BUNDLE_KEYS, call["keys"]
        assert call["scenario_id"] == SCENARIO_ID


def test_generated_test_scenario_without_test_author_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root
    )
    entry = _scenario_entry(report, SCENARIO_ID)
    assert field(entry, "result") == "fail"