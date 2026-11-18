# hotdocs-criterion: sha256:bab4c8383d1885ec2bcdbd8f17863c7dad470c7c1da2ba7d0def32abe0dbe47c
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PURPOSE_WORDS = 160


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    purpose = " ".join(["alpha"] * PURPOSE_WORDS)
    assert len(purpose.split()) == PURPOSE_WORDS
    assert "D1" not in purpose
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose
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
        "- Created.\n"
    )
    _write(comp / "component.md", component_md)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do foo.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen bar\nThen baz\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    return "specs/components/foo/component.md"


def test_ac_size_004_long_purpose_without_citations_hard_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_rel = _build_fixture(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size_004 = [f for f in findings if field(f, "rule_id") == "R-SIZE-004"]
    assert size_004, "expected an R-SIZE-004 finding, got: " + repr(findings)

    fails = [f for f in size_004 if field(f, "severity") == "fail"]
    assert fails, "expected R-SIZE-004 severity fail, got: " + repr(size_004)

    finding = fails[0]
    assert field(finding, "file") == component_rel
    assert isinstance(field(finding, "line"), int)
    message = field(finding, "message")
    assert isinstance(message, str)
    assert "150" in message, "message should name the hard-fail threshold: " + repr(message)

    # Fires on length alone: no decision-citation rule is involved here.
    assert not any(field(f, "rule_id") == "R-LINT-024" for f in findings)