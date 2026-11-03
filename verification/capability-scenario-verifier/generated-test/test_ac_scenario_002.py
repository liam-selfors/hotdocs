"""Tests for AC-SCENARIO-002 (capability-scenario-verifier)."""

import pytest

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _frontmatter(fields):
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(value)}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path

    # comp-foo: the only component declaring realizes: [P-ZERO-EDIT]
    (root / "specs/components/foo").mkdir(parents=True, exist_ok=True)
    (root / "specs/components/foo/component.md").write_text(
        _frontmatter(
            {
                "id": "comp-foo",
                "title": "Foo",
                "status": "draft",
                "owners": ["lselfors@gmail.com"],
                "sealed": "false",
                "realizes": ["P-ZERO-EDIT"],
            }
        )
        + "\n# Foo\n\nFixture component that realizes P-ZERO-EDIT.\n"
    )
    (root / "gen/foo").mkdir(parents=True, exist_ok=True)
    (root / "gen/foo/foo.py").write_text("def noop():\n    return None\n")

    # comp-bar: in the blast radius, but realizes nothing
    (root / "specs/components/bar").mkdir(parents=True, exist_ok=True)
    (root / "specs/components/bar/component.md").write_text(
        _frontmatter(
            {
                "id": "comp-bar",
                "title": "Bar",
                "status": "draft",
                "owners": ["lselfors@gmail.com"],
                "sealed": "false",
            }
        )
        + "\n# Bar\n\nFixture component that realizes nothing.\n"
    )
    (root / "gen/bar").mkdir(parents=True, exist_ok=True)
    (root / "gen/bar/bar.py").write_text("def noop():\n    return None\n")

    # comp-baz: sealed, realizes P-SEALED, real code only under pipeline/baz/
    (root / "specs/components/baz").mkdir(parents=True, exist_ok=True)
    (root / "specs/components/baz/component.md").write_text(
        _frontmatter(
            {
                "id": "comp-baz",
                "title": "Baz",
                "status": "draft",
                "owners": ["lselfors@gmail.com"],
                "sealed": "true",
                "source_path": "pipeline/baz/",
                "realizes": ["P-SEALED"],
            }
        )
        + "\n# Baz\n\nSealed fixture component; its real code lives at pipeline/baz/.\n"
    )
    (root / "pipeline/baz").mkdir(parents=True, exist_ok=True)
    (root / "pipeline/baz/baz_module.py").write_text("def answer():\n    return 42\n")
    # Deliberately no gen/baz/ directory: a sealed component has no gen/ code.

    (root / "specs/product").mkdir(parents=True, exist_ok=True)

    # P-ZERO-EDIT: realized by comp-foo (in the blast radius)
    (root / "specs/product/P-ZERO-EDIT.md").write_text(
        "---\n"
        "id: P-ZERO-EDIT\n"
        "---\n"
        "\n# Zero Edit\n"
        "\n### CS-ZERO-EDIT-001\n"
        "\nCovers: P-ZERO-EDIT\n"
        "Kind: generated-test\n"
        "\n```gherkin\n"
        "Given a widget\n"
        "When it is used\n"
        "Then it works\n"
        "```\n"
    )

    # P-UNRELATED: realized by neither comp-foo nor comp-bar
    (root / "specs/product/P-UNRELATED.md").write_text(
        "---\n"
        "id: P-UNRELATED\n"
        "---\n"
        "\n# Unrelated\n"
        "\n### CS-UNRELATED-001\n"
        "\nCovers: P-UNRELATED\n"
        "Kind: generated-test\n"
        "\n```gherkin\n"
        "Given something unrelated to the blast radius\n"
        "When it is used\n"
        "Then it works\n"
        "```\n"
    )

    # P-SEALED: realized by sealed comp-baz
    (root / "specs/product/P-SEALED.md").write_text(
        "---\n"
        "id: P-SEALED\n"
        "---\n"
        "\n# Sealed\n"
        "\n### CS-SEALED-001\n"
        "\nCovers: P-SEALED\n"
        "Kind: generated-test\n"
        "\n```gherkin\n"
        "Given the sealed component's code under its source_path\n"
        "When the scenario test imports a module from that directory\n"
        "Then it works\n"
        "```\n"
    )

    return root


def test_report_only_includes_capability_realized_by_blast_radius(repo_root):
    captured_calls = []

    def fake_test_author(bundle):
        capability_id = _get(bundle, "capability_id")
        scenario_id = _get(bundle, "scenario_id")
        captured_calls.append(capability_id)
        filename = f"test_{scenario_id.lower().replace('-', '_')}.py"
        return {
            "model_call_error": None,
            "file": {
                "path": f"verification/capabilities/{capability_id}/generated-test/{filename}",
                "content": "def test_scenario():\n    assert True\n",
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, test_author=fake_test_author
    )

    assert set(report.keys()) == {"P-ZERO-EDIT"}
    # Only the capability actually realized by the blast radius was
    # authored at all -- P-UNRELATED never got touched.
    assert captured_calls == ["P-ZERO-EDIT"]


def test_sealed_component_scenario_imports_from_source_path(repo_root):
    def fake_test_author(bundle):
        capability_id = _get(bundle, "capability_id")
        scenario_id = _get(bundle, "scenario_id")
        filename = f"test_{scenario_id.lower().replace('-', '_')}.py"
        return {
            "model_call_error": None,
            "file": {
                "path": f"verification/capabilities/{capability_id}/generated-test/{filename}",
                "content": (
                    "import baz_module\n"
                    "\n\n"
                    "def test_cs_sealed_001():\n"
                    "    assert baz_module.answer() == 42\n"
                ),
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"], repo_root, test_author=fake_test_author
    )

    assert set(report.keys()) == {"P-SEALED"}
    cap_entry = _get(report, "P-SEALED")
    assert _get(cap_entry, "overall") == "pass"

    scenarios = _get(cap_entry, "scenarios")
    assert len(scenarios) == 1
    assert _get(scenarios[0], "id") == "CS-SEALED-001"
    assert _get(scenarios[0], "result") == "pass"