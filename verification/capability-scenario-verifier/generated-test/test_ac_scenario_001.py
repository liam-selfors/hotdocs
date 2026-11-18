# hotdocs-criterion: sha256:4f684cbbde573594d90a252d7ee84072b7fdc77fbeee503db318a0655557585e
import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_mapping(value):
    if isinstance(value, Mapping):
        return dict(value)
    return dict(vars(value))


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _live_repo_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    gen = next((p for p in here.parents if p.name == "gen"), None)
    if gen is not None:
        return gen.parent
    return None


def _make_component(repo_root, slug):
    upper = slug.upper()
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " component\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n\n"
        "# " + slug.capitalize() + "\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "requirements" / ("R-" + upper + "-001.md"),
        "**R-" + upper + "-001** — The component MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        "Covers: R-" + upper + "-001\n"
        "Kind: llm-judge\n\n"
        "```gherkin\n"
        "Given the component\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "interface" / "library.md",
        "# Library\n\n```\nnoop() -> None\n```\n",
    )
    module_name = slug.replace("-", "_")
    _write(
        repo_root / "gen" / slug / (module_name + ".py"),
        "def noop():\n    return None\n",
    )


def _make_fake_dependencies(repo_root, author_log):
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = 'generated_test@1.1.0'\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(" + repr(str(author_log)) + ", 'a') as f:\n"
        "        f.write('module-author-test\\n')\n"
        "    return {\n"
        "        'component_id': bundle.get('component_id', ''),\n"
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
        "    }\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        'text': 'PASS',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )


def _copy_real_compiler(repo_root):
    live = _live_repo_root()
    if live is None:
        return
    src = live / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(src, repo_root / "pipeline" / "criterion-compiler")


def _make_capability(repo_root):
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n\n"
        "# Capability X\n\n"
        "A product capability realized by two components.\n\n"
        "### CS-X-001\n\n"
        "Covers: P-X\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the assembled system\n"
        "When the capability is exercised\n"
        "Then it works end to end\n"
        "```\n",
    )


def test_generated_test_scenario_runs_and_is_keyed_by_capability(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.log"
    callable_log = logs / "callable.log"
    marker = logs / "ran.marker"

    _make_component(repo_root, "alpha")
    _make_component(repo_root, "beta")
    _make_capability(repo_root)
    _make_fake_dependencies(repo_root, author_log)
    _copy_real_compiler(repo_root)

    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(marker)) + ", 'a') as f:\n"
        "        f.write('ran\\n')\n"
        "    assert True\n"
    )

    def fake_test_author(bundle):
        try:
            sid = field(bundle, "scenario_id")
        except (KeyError, AttributeError):
            sid = "<missing>"
        with open(callable_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"scenario_id": sid}) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": test_content,
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha", "comp-beta"], repo_root, test_author=fake_test_author
    )

    # The injected test_author was dispatched exactly once, for the scenario.
    assert callable_log.is_file(), "test_author was never called"
    calls = [json.loads(line) for line in callable_log.read_text().splitlines() if line.strip()]
    assert len(calls) == 1
    assert calls[0]["scenario_id"] == "CS-X-001"

    # The produced test was actually run.
    assert marker.is_file(), "the generated scenario test was never run"
    assert "ran" in marker.read_text()

    # Keyed by P-id, never by either component.
    mapping = as_mapping(report)
    keys = set(mapping.keys())
    assert keys == {"P-X"}
    for comp in ("comp-alpha", "comp-beta", "alpha", "beta"):
        assert comp not in keys

    entry = mapping["P-X"]
    assert field(entry, "overall") == "pass"
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert field(scenario, "id") == "CS-X-001"
    assert field(scenario, "kind") == "generated-test"
    assert field(scenario, "result") == "pass"