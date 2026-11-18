# hotdocs-criterion: sha256:39417c6c89ab90006148579eff477d5b46f879ef1fa8b41d89e7ad5ab1f1cb4e
import json
import shutil
from pathlib import Path

import capability_scenario_verifier


EXPECTED_BUNDLE_KEYS = {"capability_id", "scenario_id", "covers", "kind", "gherkin", "file"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def capability_entry(report, capability_id):
    if isinstance(report, dict):
        return report[capability_id]
    try:
        return report[capability_id]
    except (TypeError, KeyError):
        return getattr(report, capability_id)


def scenario_result(report, capability_id, scenario_id):
    entry = capability_entry(report, capability_id)
    for scenario in field(entry, "scenarios"):
        if field(scenario, "id") == scenario_id:
            return field(scenario, "result")
    raise AssertionError("scenario " + scenario_id + " missing from report")


def _live_repo_root():
    gen = next(
        p for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    return gen.parent


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(repo_root):
    # Real compiler copied from the live repository.
    live_compiler = _live_repo_root() / "pipeline" / "criterion-compiler"
    if live_compiler.is_dir():
        shutil.copytree(
            live_compiler,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    # Fake test-author dependency (flat module shape).
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = " + repr("generated_test@1.1.0") + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        " + repr("component_id") + ": None,\n"
        "        " + repr("criterion_id") + ": bundle[" + repr("criterion_id") + "],\n"
        "        " + repr("model") + ": model,\n"
        "        " + repr("seed") + ": seed,\n"
        "        " + repr("prompt_version") + ": " + repr("v1") + ",\n"
        "        " + repr("cache_hit") + ": False,\n"
        "        " + repr("file") + ": {\n"
        "            " + repr("path") + ": "
        + repr("verification/capabilities/P-X/generated-test/test_cs_x_001.py") + ",\n"
        "            " + repr("content") + ": "
        + repr("def test_x():\n    assert True\n") + ",\n"
        "        },\n"
        "        " + repr("model_call_error") + ": None,\n"
        "    }\n",
    )

    # Fake llm-endpoint dependency (flat module shape).
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        " + repr("text") + ": " + repr("PASS") + ",\n"
        "        " + repr("model") + ": model,\n"
        "        " + repr("backend") + ": " + repr("fake") + ",\n"
        "        " + repr("model_call_error") + ": None,\n"
        "    }\n",
    )

    # A non-sealed component realizing P-X.
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# comp-foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST exist.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a value is 1\n"
        "When nothing happens\n"
        "Then value equals 1\n"
        "```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")

    # The capability, with one generated-test scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: X capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# P-X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo component\n"
        "When it runs\n"
        "Then it succeeds\n"
        "```\n",
    )


def make_recording_test_author(log_path):
    def test_author(bundle):
        if isinstance(bundle, dict):
            keys = sorted(bundle.keys())
        else:
            keys = sorted(vars(bundle).keys())
        with open(log_path, "a") as fh:
            fh.write(json.dumps(keys) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    return test_author


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_generated_test_scenario_dispatched_fresh_on_every_call(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)
    log_path = tmp_path / "test_author_calls.log"
    test_author = make_recording_test_author(log_path)

    report1 = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=test_author
    )
    assert len(read_log(log_path)) == 1
    capability_entry(report1, "P-X")

    report2 = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=test_author
    )
    capability_entry(report2, "P-X")

    calls = read_log(log_path)
    assert len(calls) == 2, "test_author must be invoked on both calls, got " + repr(calls)


def test_bundle_keys_are_exactly_the_scenario_shape(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)
    log_path = tmp_path / "test_author_calls.log"
    test_author = make_recording_test_author(log_path)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=test_author
    )

    calls = read_log(log_path)
    assert len(calls) >= 1
    for keys in calls:
        assert set(keys) == EXPECTED_BUNDLE_KEYS
        assert len(keys) == len(EXPECTED_BUNDLE_KEYS)


def test_generated_test_scenario_without_test_author_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=None
    )

    assert scenario_result(report, "P-X", "CS-X-001") == "fail"