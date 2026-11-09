import pathlib

import pytest

import spec_bundle_assembler


PURPOSE_MARKER = "PURPOSE_MARKER_ALPHA_7321"
SCOPE_MARKER = "SCOPE_MARKER_BETA_8842"
RATIONALE_MARKER = "RATIONALE_MARKER_GAMMA_1193"
OPENQ_MARKER = "OPENQ_MARKER_DELTA_5567"
CHANGELOG_MARKER = "CHANGELOG_MARKER_EPSILON_9924"


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _build_corpus(repo_root: pathlib.Path) -> None:
    specs_dir = repo_root / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "glossary.md").write_text(
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n"
    )

    comp_dir = specs_dir / "components" / "foo"
    comp_dir.mkdir(parents=True)

    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Foo doubles a number. {PURPOSE_MARKER}.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"Foo only handles integer doubling. {SCOPE_MARKER}.\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"This design was chosen for historical reasons. {RATIONALE_MARKER}.\n"
        "\n"
        "## Open questions\n"
        "\n"
        f"Should Foo support floats? {OPENQ_MARKER}.\n"
        "\n"
        "## Change log\n"
        "\n"
        f"- 2024-01-01: initial version. {CHANGELOG_MARKER}.\n"
    )

    requirements_dir = comp_dir / "requirements"
    requirements_dir.mkdir()
    (requirements_dir / "R-FOO-001.md").write_text(
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
    )

    acceptance_dir = comp_dir / "acceptance"
    acceptance_dir.mkdir()
    (acceptance_dir / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n"
    )

    interface_dir = comp_dir / "interface"
    interface_dir.mkdir()
    (interface_dir / "library.md").write_text(
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
    )

    (comp_dir / "constraints.md").write_text(
        "# Constraints\n"
        "\n"
        "None.\n"
    )


def test_cold_spec_includes_purpose_scope_excludes_rationale_openq_changelog(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    spec_text = _field(bundle, "spec")
    assert spec_text is not None

    assert PURPOSE_MARKER in spec_text
    assert SCOPE_MARKER in spec_text

    assert RATIONALE_MARKER not in spec_text
    assert OPENQ_MARKER not in spec_text
    assert CHANGELOG_MARKER not in spec_text