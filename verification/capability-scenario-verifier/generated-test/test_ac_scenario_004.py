# hotdocs-criterion: sha256:c83f257412724395f078f2c82cdfcb38000834d22ebdfb77a6701031d554c8ed
import sys
from pathlib import Path

import capability_scenario_verifier


EXPECTED_BUNDLE_KEYS = {"capability_id", "scenario_id", "covers", "kind", "gherkin", "file"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def build_repo(repo_root):
    repo_root = Path(repo_root)

    # Planted python adapter, so no criterion depends on the tool's own.
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # A non-sealed component realizing P-X, with its code under gen/foo/.
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
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
    write(
        repo_root / "gen" / "foo" / "foo.py",
        "def value():\n"
        "    return 1\n",
    )

    # The capability, under specs/product/, with one generated-test scenario.
    write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: X capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# P-X\n"
        "\n"
        "A fixture capability.\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo component\n"
        "When its value is read\n"
        "Then the value is one\n"
        "```\n",
    )

    # Fake test-author and llm-endpoint modules at their dependency paths.
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = 'generated_test@3.0.0'\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': 'verification/capabilities/P-X/generated-test/test_cs_x_001.py',\n"
        "            'content': 'def test_x():\\n    assert True\\n',\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )
    return repo_root


def make_test_author(calls):
    def test_author(bundle):
        calls.append(dict(bundle) if isinstance(bundle, dict) else bundle)
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    return test_author


def scenario_entry(report, capability_id, scenario_id):
    cap = report[capability_id] if isinstance(report, dict) else getattr(report, capability_id)
    for entry in field(cap, "scenarios"):
        if field(entry, "id") == scenario_id:
            return entry
    raise AssertionError("scenario " + repr(scenario_id) + " not in report: " + repr(report))


def test_generated_test_dispatched_on_every_call(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    calls = []
    test_author = make_test_author(calls)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    assert len(calls) == 1, "test_author not invoked on first call: " + repr(calls)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    assert len(calls) == 2, (
        "test_author not invoked on second call with unchanged content: " + repr(calls)
    )


def test_bundle_keys_are_exactly_the_capability_shape(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    calls = []
    test_author = make_test_author(calls)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )

    assert len(calls) >= 1, "test_author was never dispatched"
    for bundle in calls:
        assert isinstance(bundle, dict), "bundle is not a dict: " + repr(bundle)
        assert set(bundle.keys()) == EXPECTED_BUNDLE_KEYS, (
            "bundle keys " + repr(sorted(bundle.keys()))
            + " != " + repr(sorted(EXPECTED_BUNDLE_KEYS))
        )


def test_generated_test_without_test_author_fails(tmp_path):
    repo_root = build_repo(tmp_path / "repo")

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo_root)

    entry = scenario_entry(report, "P-X", "CS-X-001")
    assert field(entry, "result") == "fail", "expected fail, got " + repr(entry)