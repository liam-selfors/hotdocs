# hotdocs-criterion: sha256:bab4c8383d1885ec2bcdbd8f17863c7dad470c7c1da2ba7d0def32abe0dbe47c
import re
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    words = ["word"] * 160
    purpose_text = " ".join(words)
    assert len(purpose_text.split()) == 160
    assert re.search(r"\bD\d+\b", purpose_text) is None

    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose_text
        + "\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: foo.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial.\n"
    )
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", component_md)
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do foo.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo happens\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a foo.\n",
    )


def test_ac_size_004_long_purpose_without_citation_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size4 = [f for f in findings if field(f, "rule_id") == "R-SIZE-004"]
    assert size4, "expected an R-SIZE-004 finding, got: " + repr(findings)

    fails = [f for f in size4 if field(f, "severity") == "fail"]
    assert fails, "expected R-SIZE-004 to fail (not merely warn): " + repr(size4)

    finding = fails[0]
    assert field(finding, "file") == "specs/components/foo/component.md"
    assert isinstance(field(finding, "line"), int)
    assert "150" in str(field(finding, "message"))