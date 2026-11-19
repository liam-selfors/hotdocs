# hotdocs-criterion: sha256:4f684cbbde573594d90a252d7ee84072b7fdc77fbeee503db318a0655557585e
import json
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def report_keys(report):
    if isinstance(report, dict):
        return set(report.keys())
    if hasattr(report, "keys"):
        return set(report.keys())
    return set(vars(report).keys())


def report_entry(report, key):
    if isinstance(report, dict) or hasattr(report, "__getitem__"):
        return report[key]
    return getattr(report, key)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_component(repo_root, slug, capability_id):
    component_md = (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [" + capability_id + "]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "A fixture component.\n"
    )
    write(repo_root / "specs" / "components" / slug / "component.md", component_md)
    module_name = slug.replace("-", "_")
    write(
        repo_root / "gen" / slug / (module_name + ".py"),
        "def hello():\n    return " + repr(slug) + "\n",
    )


def build_capability(repo_root):
    product_md = (
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "A fixture product capability.\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a fully assembled system\n"
        "When the user does the thing\n"
        "Then the thing is done\n"
        "```\n"
    )
    write(repo_root / "specs" / "product" / "x.md", product_md)


def build_fake_dependencies(repo_root):
    fake_test_author = (
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        'component_id': 'comp-unused',\n"
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
        "    }\n"
    )
    write(repo_root / "gen" / "test-author" / "test_author.py", fake_test_author)
    fake_llm_endpoint = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        'text': 'ok',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", fake_llm_endpoint)


def test_generated_test_scenario_is_run_and_keyed_by_capability(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_component(repo_root, "alpha", "P-X")
    build_component(repo_root, "beta", "P-X")
    build_capability(repo_root)
    build_fake_dependencies(repo_root)

    call_log = tmp_path / "test_author_calls.log"
    run_marker = tmp_path / "generated_test_ran.log"

    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(run_marker)) + ", 'a') as handle:\n"
        "        handle.write('ran\\n')\n"
        "    assert True\n"
    )

    def fake_test_author(bundle):
        with open(str(call_log), "a") as handle:
            scenario_id = None
            if isinstance(bundle, dict):
                scenario_id = bundle.get("scenario_id")
            else:
                scenario_id = getattr(bundle, "scenario_id", None)
            handle.write(json.dumps({"scenario_id": scenario_id}) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": test_content,
            },
        }

    def fake_judge(bundle):
        raise AssertionError("judge must not be called for a generated-test scenario")

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha", "comp-beta"],
        repo_root,
        judge=fake_judge,
        test_author=fake_test_author,
    )

    # The fake test_author was dispatched exactly once, for the one scenario.
    assert call_log.is_file(), "test_author was never called"
    calls = [line for line in call_log.read_text().splitlines() if line.strip()]
    assert len(calls) == 1
    assert json.loads(calls[0])["scenario_id"] == "CS-X-001"

    # The produced test was actually run.
    assert run_marker.is_file(), "the generated scenario test was never run"
    assert "ran" in run_marker.read_text()

    # Keyed by the capability's P-id, never by either component.
    keys = report_keys(report)
    assert keys == {"P-X"}
    assert "comp-alpha" not in keys
    assert "comp-beta" not in keys
    assert "alpha" not in keys
    assert "beta" not in keys

    entry = report_entry(report, "P-X")
    assert field(entry, "overall") == "pass"

    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert field(scenario, "id") == "CS-X-001"
    assert field(scenario, "kind") == "generated-test"
    assert field(scenario, "result") == "pass"