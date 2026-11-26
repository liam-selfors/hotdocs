# hotdocs-criterion: sha256:df4fd0ca5f81013ca6862d9152ee5c8622e3a0c8296b117625fb21125478c2fe
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    specs = repo_root / "specs"

    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — a small thing used in tests.\n",
    )

    write(
        specs / "architecture" / "target.md",
        "---\n"
        "id: arch-target\n"
        "title: Target Document\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Target Document\n"
        "\n"
        "Some introductory text.\n"
        "\n"
        "## Query surface\n"
        "\n"
        "The query surface is described here.\n",
    )

    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo() -> None\n"
        "```\n",
    )

    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST behave as\n"
        "  `specs/architecture/target.md`'s \"Query surface\" section states.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — Foo MUST behave as\n"
        "  `specs/architecture/target.md`'s \"Nonexistent Heading\" section states.\n",
    )

    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When foo runs\n"
        "Then it behaves\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When foo runs\n"
        "Then it behaves\n"
        "```\n",
    )


def norm(p):
    return str(p).replace("\\", "/")


def test_ac_cite_002_only_missing_section_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite2 = [f for f in findings if field(f, "rule_id") == "R-CITE-002"]

    good_file = "specs/components/foo/requirements/R-FOO-001.md"
    bad_file = "specs/components/foo/requirements/R-FOO-002.md"

    flagged_files = [norm(field(f, "file")) for f in cite2]

    assert good_file not in flagged_files, (
        "the valid 'Query surface' citation must not be flagged: " + repr(cite2)
    )
    assert flagged_files == [bad_file], (
        "expected exactly one R-CITE-002 finding, on the "
        "'Nonexistent Heading' citation: " + repr(cite2)
    )

    finding = cite2[0]
    assert field(finding, "severity") in ("fail", "warn")
    assert isinstance(field(finding, "line"), int)
    assert isinstance(field(finding, "message"), str)