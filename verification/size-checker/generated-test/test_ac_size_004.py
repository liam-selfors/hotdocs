"""AC-SIZE-004 (Covers: R-SIZE-004).

Given a component whose Purpose section is 160 words long, with no
decision citation anywhere in it, when check(repo_root) runs, then it
fails with R-SIZE-004 naming the hard-fail threshold (150) -- the rule
fires on length alone, independently of any decision-citation rule.
"""

import re
from pathlib import Path

import size_checker


COMPONENT_SLUG = "foo"
COMPONENT_REL = "specs/components/foo/component.md"
HARD_FAIL_THRESHOLD = 150


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _purpose_text(word_count):
    words = [f"word{i}" for i in range(word_count)]
    lines = []
    for start in range(0, word_count, 10):
        lines.append(" ".join(words[start:start + 10]))
    return "\n".join(lines)


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path, purpose_words: int) -> str:
    purpose = _purpose_text(purpose_words)
    # Sanity on the fixture itself: exact length, no decision citation.
    assert len(purpose.split()) == purpose_words
    assert re.search(r"\bD\d+\b", purpose) is None

    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose}\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: foo things.\n"
        "- Out of scope: everything else.\n"
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
        "- Initial version.\n"
    )
    comp_dir = root / "specs" / "components" / COMPONENT_SLUG
    _write(comp_dir / "component.md", component_md)
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do a foo thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a foo\nWhen it runs\nThen it does a foo thing\n```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo thing** — a thing foo does.\n",
    )
    return purpose


def _size_004_findings(findings):
    return [
        f for f in findings
        if field(f, "rule_id") == "R-SIZE-004"
        and field(f, "file") == COMPONENT_REL
    ]


def test_purpose_of_160_words_without_citation_fails_r_size_004(tmp_path):
    _build_repo(tmp_path, 160)

    findings = size_checker.check(tmp_path)
    assert isinstance(findings, list)

    matched = _size_004_findings(findings)
    fails = [f for f in matched if field(f, "severity") == "fail"]
    assert fails, f"expected a fail-severity R-SIZE-004 finding, got {findings!r}"

    finding = fails[0]
    assert str(HARD_FAIL_THRESHOLD) in field(finding, "message"), (
        "R-SIZE-004 failure message must name the hard-fail threshold 150: "
        f"{field(finding, 'message')!r}"
    )
    line = field(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1

    # Every finding has exactly the documented keys/fields.
    for f in findings:
        for key in ("rule_id", "severity", "file", "line", "message"):
            field(f, key)
        assert field(f, "severity") in ("fail", "warn")


def test_purpose_at_exactly_150_words_does_not_hard_fail(tmp_path):
    _build_repo(tmp_path, HARD_FAIL_THRESHOLD)

    findings = size_checker.check(tmp_path)
    matched = _size_004_findings(findings)
    assert not [f for f in matched if field(f, "severity") == "fail"], (
        f"150 words is not above the hard-fail cap: {matched!r}"
    )


def test_purpose_of_151_words_hard_fails(tmp_path):
    _build_repo(tmp_path, HARD_FAIL_THRESHOLD + 1)

    findings = size_checker.check(tmp_path)
    matched = _size_004_findings(findings)
    fails = [f for f in matched if field(f, "severity") == "fail"]
    assert fails, f"151 words is above the hard-fail cap: {findings!r}"
    assert str(HARD_FAIL_THRESHOLD) in field(fails[0], "message")