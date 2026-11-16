"""AC-SCENARIO-002 (Covers: R-SCENARIO-002).

1. The capability-intersection lookup reports only capabilities whose
   realizing set intersects the blast radius, where `realizes` is read
   from each component's own component.md.
2. A sealed component's code directory is its frontmatter `source_path`
   (not gen/<slug>/), so a capability scenario test importing a module
   from there passes.
"""

import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

import capability_scenario_verifier


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def field(value, name, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def report_keys(report):
    if isinstance(report, Mapping):
        return sorted(report.keys())
    if hasattr(report, "keys"):
        return sorted(report.keys())
    return sorted(k for k in vars(report) if not k.startswith("_"))


def report_entry(report, key):
    if isinstance(report, Mapping):
        return report[key]
    if hasattr(report, "__getitem__"):
        return report[key]
    return getattr(report, key)


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy_real_compiler(repo_root: Path):
    tool_root = _tool_root()
    if tool_root is None:
        return
    src = tool_root / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


FAKE_TEST_AUTHOR = '''\
def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    criterion_id = bundle["criterion_id"]
    slug = criterion_id.lower().replace("-", "_")
    return {
        "component_id": bundle.get("component_id", ""),
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/capabilities/fake/generated-test/test_" + slug + ".py",
            "content": "def test_x():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''

FAKE_LLM_ENDPOINT = '''\
def complete(prompt, model, *, backend=None, **params):
    return {
        "text": "pass",
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }
'''


def _install_fake_dependencies(repo_root: Path):
    _write(repo_root / "gen" / "test-author" / "test_author.py", FAKE_TEST_AUTHOR)
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT)
    _copy_real_compiler(repo_root)


def _write_component(repo_root: Path, slug: str, realizes=None, sealed=False,
                     source_path=None):
    upper = slug.upper()
    lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {slug.capitalize()} fixture",
        "status: draft",
        "owners: [fixture-owner]",
        "depends_on: []",
    ]
    if realizes is not None:
        lines.append("realizes: [" + ", ".join(realizes) + "]")
    if sealed:
        lines.append("sealed: true")
        lines.append(f"source_path: {source_path}")
    else:
        lines.append("sealed: false")
    lines.append("---")
    lines.append("")
    lines.append(f"# comp-{slug}")
    lines.append("")
    lines.append("Synthetic fixture component.")
    lines.append("")
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md", "\n".join(lines))
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST exist.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: llm-judge\n\n"
        "```gherkin\nGiven the component\nWhen it is inspected\n"
        "Then it exists\n```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nnoop() -> None\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


def _write_capability(repo_root: Path, name: str, cap_id: str):
    suffix = cap_id[len("P-"):]
    scenario_id = f"CS-{suffix}-001"
    text = (
        "---\n"
        f"id: {cap_id}\n"
        f"title: {name} capability\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        "---\n"
        "\n"
        f"# {cap_id}\n"
        "\n"
        "Synthetic fixture capability.\n"
        "\n"
        f"### {scenario_id}\n"
        "\n"
        f"Covers: {cap_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the capability is realized\n"
        "When its scenario runs\n"
        "Then it holds\n"
        "```\n"
    )
    _write(repo_root / "specs" / "product" / f"{name}.md", text)
    return scenario_id


def _make_test_author(log_path: Path, contents: dict):
    """Single-bundle-arg callable (D65); logs each call to a file."""

    def test_author(bundle):
        capability_id = field(bundle, "capability_id")
        scenario_id = field(bundle, "scenario_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"capability_id": capability_id,
                                 "scenario_id": scenario_id}) + "\n")
        slug = str(scenario_id).lower().replace("-", "_")
        content = contents.get(scenario_id, "def test_x():\n    assert True\n")
        return {
            "model_call_error": None,
            "file": {
                "path": f"verification/capabilities/{capability_id}/"
                        f"generated-test/test_{slug}.py",
                "content": content,
            },
        }

    return test_author


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in
            log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_report_keys_only_capabilities_realized_within_blast_radius(
        tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)
    _install_fake_dependencies(repo_root)

    # comp-foo realizes P-ZERO-EDIT; comp-bar declares no realizes at all.
    _write_component(repo_root, "foo", realizes=["P-ZERO-EDIT"])
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    _write_component(repo_root, "bar", realizes=None)
    _write(repo_root / "gen" / "bar" / "bar.py", "VALUE = 2\n")
    # P-UNRELATED is realized by neither foo nor bar (only by a component
    # outside the blast radius).
    _write_component(repo_root, "qux", realizes=["P-UNRELATED"])
    _write(repo_root / "gen" / "qux" / "qux.py", "VALUE = 3\n")

    _write_capability(repo_root, "zero-edit", "P-ZERO-EDIT")
    _write_capability(repo_root, "unrelated", "P-UNRELATED")

    log_path = tmp_path / "test_author_calls.log"
    test_author = _make_test_author(log_path, {})

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, judge=None, test_author=test_author,
    )

    assert report_keys(report) == ["P-ZERO-EDIT"]
    assert "P-UNRELATED" not in report_keys(report)

    calls = _read_log(log_path)
    assert all(c["capability_id"] != "P-UNRELATED" for c in calls)


def test_sealed_component_code_directory_is_its_source_path(
        tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)
    _install_fake_dependencies(repo_root)

    _write_component(repo_root, "baz", realizes=["P-SEALED"], sealed=True,
                     source_path="pipeline/baz/")
    _write(
        repo_root / "pipeline" / "baz" / "baz_core.py",
        'MARKER = "sealed-baz-source"\n',
    )
    assert not (repo_root / "gen" / "baz").exists()

    scenario_id = _write_capability(repo_root, "sealed", "P-SEALED")

    log_path = tmp_path / "test_author_calls.log"
    test_content = (
        "import baz_core\n"
        "\n"
        "\n"
        "def test_imports_sealed_source():\n"
        '    assert baz_core.MARKER == "sealed-baz-source"\n'
    )
    test_author = _make_test_author(log_path, {scenario_id: test_content})

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"], repo_root, judge=None, test_author=test_author,
    )

    assert report_keys(report) == ["P-SEALED"]
    entry = report_entry(report, "P-SEALED")
    scenarios = list(field(entry, "scenarios") or [])
    matching = [s for s in scenarios if field(s, "id") == scenario_id]
    assert len(matching) == 1, scenarios
    scenario = matching[0]
    assert field(scenario, "kind") == "generated-test"
    assert field(scenario, "result") == "pass", scenario
    assert field(entry, "overall") == "pass"

    calls = _read_log(log_path)
    assert any(c["scenario_id"] == scenario_id for c in calls)