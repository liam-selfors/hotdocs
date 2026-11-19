# hotdocs-criterion: sha256:5fcf42cbd0644d6f12d0d7b16eef322325c0242756d165e9fe6b649bb97f9443
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SCENARIO_ID = "CS-X-001"
CAPABILITY_ID = "P-X"
EXPECTED_BUNDLE_KEYS = {"capability_id", "scenario_id", "covers", "kind", "gherkin", "file"}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root):
    repo_root = Path(repo_root)

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

    # A non-sealed component realizing P-X.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "def noop():\n    return None\n")

    # The product capability with one generated-test scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [team]\n"
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
        "Then it works\n"
        "```\n",
    )

    # Fake test-author module (real signature and full result shape).
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        \"component_id\": None,\n"
        "        \"criterion_id\": bundle[\"criterion_id\"],\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\"path\": " + repr("verification/capabilities/P-X/generated-test/test_cs_x_001.py") + ",\n"
        "                 \"content\": " + repr("def test_x():\n    assert True\n") + "},\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )

    # Fake llm-endpoint module (real signature and full response shape).
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )
    return repo_root


def _make_test_author(log_path, bundles):
    def test_author(bundle):
        with open(log_path, "a") as fh:
            fh.write("called\n")
        bundles.append(dict(bundle) if isinstance(bundle, dict) else bundle)
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    return test_author


def _calls(log_path):
    if not Path(log_path).exists():
        return 0
    return len([line for line in Path(log_path).read_text().splitlines() if line.strip()])


def _scenario_entry(report, scenario_id):
    cap = field(report, CAPABILITY_ID)
    scenarios = field(cap, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == scenario_id]
    assert len(matches) == 1, scenarios
    return matches[0]


def test_generated_test_dispatched_fresh_on_every_call(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")
    log_path = tmp_path / "author_calls.log"
    bundles = []
    test_author = _make_test_author(log_path, bundles)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    assert _calls(log_path) == 1

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )
    assert _calls(log_path) == 2


def test_bundle_keys_are_exactly_the_scenario_shape(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")
    log_path = tmp_path / "author_calls.log"
    bundles = []
    test_author = _make_test_author(log_path, bundles)

    capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=test_author
    )

    assert _calls(log_path) == 1
    assert len(bundles) == 1
    bundle = bundles[0]
    assert isinstance(bundle, dict)
    assert set(bundle.keys()) == EXPECTED_BUNDLE_KEYS
    assert bundle["scenario_id"] == SCENARIO_ID
    assert bundle["capability_id"] == CAPABILITY_ID


def test_generated_test_without_test_author_fails(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo_root)

    entry = _scenario_entry(report, SCENARIO_ID)
    assert field(entry, "result") == "fail"