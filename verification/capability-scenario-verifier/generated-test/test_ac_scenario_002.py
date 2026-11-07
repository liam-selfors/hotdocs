"""AC-SCENARIO-002"""

from pathlib import Path

import pytest

import capability_scenario_verifier


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_zero_edit_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "sealed: false\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n\n"
        "# Foo\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "sealed: true\n"
        "source_path: pipeline/bar-impl/\n"
        "---\n\n"
        "# Bar\n",
    )
    _write(
        repo_root / "specs" / "product" / "P-ZERO-EDIT.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero Edit\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "---\n\n"
        "# Zero Edit\n\n"
        "### CS-ZERO-EDIT-001\n\n"
        "Covers: P-ZERO-EDIT\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget exists\n"
        "When it is checked\n"
        "Then it passes\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "product" / "P-UNRELATED.md",
        "---\n"
        "id: P-UNRELATED\n"
        "title: Unrelated\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "---\n\n"
        "# Unrelated\n\n"
        "### CS-UNRELATED-001\n\n"
        "Covers: P-UNRELATED\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a gadget exists\n"
        "When it is checked\n"
        "Then it passes\n"
        "```\n",
    )


def _build_sealed_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "components" / "baz" / "component.md",
        "---\n"
        "id: comp-baz\n"
        "title: Baz\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "sealed: true\n"
        "source_path: pipeline/baz/\n"
        "realizes: [P-SEALED]\n"
        "---\n\n"
        "# Baz\n",
    )
    _write(
        repo_root / "specs" / "product" / "P-SEALED.md",
        "---\n"
        "id: P-SEALED\n"
        "title: Sealed\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "---\n\n"
        "# Sealed\n\n"
        "### CS-SEALED-001\n\n"
        "Covers: P-SEALED\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a sealed component exists\n"
        "When its scenario test imports its source module\n"
        "Then it passes\n"
        "```\n",
    )
    _write(repo_root / "pipeline" / "baz" / "baz.py", "VALUE = 42\n")


def test_report_only_includes_realized_capability(tmp_path):
    repo_root = tmp_path / "repo"
    _build_zero_edit_fixture(repo_root)

    calls = []

    def fake_test_author(bundle):
        calls.append(_get(bundle, "capability_id"))
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-ZERO-EDIT/generated-test/test_cs_zero_edit_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, test_author=fake_test_author,
    )

    assert set(report.keys()) == {"P-ZERO-EDIT"}
    assert calls == ["P-ZERO-EDIT"]
    assert _get(report["P-ZERO-EDIT"], "overall") == "pass"


def test_sealed_component_scenario_imports_from_source_path(tmp_path):
    repo_root = tmp_path / "repo"
    _build_sealed_fixture(repo_root)

    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-SEALED/generated-test/test_cs_sealed_001.py",
                "content": (
                    "import baz\n\n"
                    "def test_x():\n"
                    "    assert baz.VALUE == 42\n"
                ),
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"], repo_root, test_author=fake_test_author,
    )

    assert _get(report["P-SEALED"], "overall") == "pass"
    scenarios = _get(report["P-SEALED"], "scenarios")
    assert len(scenarios) == 1
    assert _get(scenarios[0], "result") == "pass"