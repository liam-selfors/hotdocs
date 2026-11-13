import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

import capability_scenario_verifier


GENERATED_TEST_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_mapping(report):
    if isinstance(report, Mapping):
        return dict(report)
    for attr in ("capabilities", "report", "data"):
        inner = getattr(report, attr, None)
        if isinstance(inner, Mapping):
            return dict(inner)
    if hasattr(report, "items"):
        return dict(report.items())
    return dict(vars(report))


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component(repo_root: Path, slug: str):
    upper = slug.upper()
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n\n"
        f"# {slug.capitalize()}\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: llm-judge\n\n"
        "```gherkin\nGiven the component\nWhen it is inspected\nThen it exists\n```\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "interface" / "library.md",
        f"# Library\n\n```\nrun_{slug}() -> None\n```\n",
    )
    _write(repo_root / "specs" / "components" / slug / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "gen" / slug / f"{slug}.py",
        f"def run_{slug}():\n    return None\n",
    )


def _capability(repo_root: Path):
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n\n"
        "# Capability X\n\n"
        "The system delivers capability X.\n\n"
        "### CS-X-001\n\n"
        "Covers: P-X\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the fully assembled system\n"
        "When capability X is exercised\n"
        "Then it works\n"
        "```\n",
    )


def _fake_dependencies(repo_root: Path, author_log: Path, endpoint_log: Path):
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "import json\n\n"
        f"_LOG = {str(author_log)!r}\n\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'criterion_id': bundle.get('criterion_id') if isinstance(bundle, dict) else None}) + '\\n')\n"
        "    return {\n"
        "        'component_id': None,\n"
        "        'criterion_id': bundle.get('criterion_id') if isinstance(bundle, dict) else None,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        f"            'path': {GENERATED_TEST_PATH!r},\n"
        "            'content': 'def test_x():\\n    assert True\\n',\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "import json\n\n"
        f"_LOG = {str(endpoint_log)!r}\n\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'model': model}) + '\\n')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )


def _copy_compiler(repo_root: Path):
    root = _tool_root()
    if root is None:
        return
    src = root / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def test_ac_scenario_001_capability_scenario_run_keyed_by_p_id(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()

    author_log = logs / "author_test_module.log"
    endpoint_log = logs / "llm_endpoint.log"
    injected_log = logs / "injected_test_author.log"
    ran_marker = logs / "generated_test_ran.marker"

    _component(repo_root, "alpha")
    _component(repo_root, "beta")
    _capability(repo_root)
    _fake_dependencies(repo_root, author_log, endpoint_log)
    _copy_compiler(repo_root)
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Term** — a term.\n")

    test_content = (
        "import pathlib\n\n"
        "def test_x():\n"
        f"    pathlib.Path({str(ran_marker)!r}).write_text('ran')\n"
        "    assert True\n"
    )

    def fake_test_author(bundle):
        sid = bundle.get("scenario_id") if isinstance(bundle, dict) else getattr(bundle, "scenario_id", None)
        with open(injected_log, "a") as fh:
            fh.write(json.dumps({"scenario_id": sid}) + "\n")
        return {
            "model_call_error": None,
            "file": {"path": GENERATED_TEST_PATH, "content": test_content},
        }

    def fake_judge(bundle):
        return {"result": "pass", "rationale": "fake judge"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha", "comp-beta"],
        repo_root,
        judge=fake_judge,
        test_author=fake_test_author,
    )

    mapping = as_mapping(report)

    # Keyed by the capability's P-id, never by either component.
    assert set(mapping.keys()) == {"P-X"}
    for forbidden in ("comp-alpha", "comp-beta", "alpha", "beta"):
        assert forbidden not in mapping

    entry = mapping["P-X"]
    assert field(entry, "overall") == "pass"

    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert field(scenario, "id") == "CS-X-001"
    assert field(scenario, "kind") == "generated-test"
    assert field(scenario, "result") == "pass"

    # The injected test_author was dispatched for this one scenario.
    assert injected_log.exists(), "injected test_author was never called"
    calls = [json.loads(line) for line in injected_log.read_text().splitlines() if line.strip()]
    assert len(calls) == 1
    assert calls[0]["scenario_id"] == "CS-X-001"

    # The produced test was actually run, not merely produced.
    assert ran_marker.exists(), "the generated scenario test was never executed"
    assert ran_marker.read_text() == "ran"