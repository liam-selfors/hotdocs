# hotdocs-criterion: sha256:3ad487cc9e03cd8fe11f31166f5a260e20575e73a2f90ce387e102f53e7ae5e2
"""AC-SIZE-007: per-file word count (R-SIZE-003) warns above 250 and fails
above 500, naming each acceptance file and its own word count."""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _acceptance_text(ac_id: str, covers: str, total_words: int) -> str:
    header = "# " + ac_id + "\n\nCovers: " + covers + "\nKind: generated-test\n\n"
    header_words = len(header.split())
    filler_count = total_words - header_words
    assert filler_count > 0
    lines = []
    words = ["alpha"] * filler_count
    for i in range(0, len(words), 10):
        lines.append(" ".join(words[i:i + 10]))
    text = header + "\n".join(lines) + "\n"
    assert len(text.split()) == total_words
    return text


def _build_fixture(repo_root: Path) -> None:
    comp = repo_root / "specs" / "components" / "foo"
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
        "Foo does a small thing for testing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the small thing.\n"
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
    _write(comp / "component.md", component_md)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the first thing.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do the second thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        _acceptance_text("AC-FOO-001", "R-FOO-001", 300),
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        _acceptance_text("AC-FOO-002", "R-FOO-002", 520),
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond defaults.\n",
    )


def test_ac_size_007_per_file_warn_and_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    warn_file = "specs/components/foo/acceptance/AC-FOO-001.md"
    fail_file = "specs/components/foo/acceptance/AC-FOO-002.md"

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    first = [f for f in size3 if field(f, "file") == warn_file]
    second = [f for f in size3 if field(f, "file") == fail_file]

    assert len(first) == 1, size3
    assert len(second) == 1, size3

    assert field(first[0], "severity") == "warn"
    assert field(second[0], "severity") == "fail"

    assert "300" in field(first[0], "message")
    assert "520" in field(second[0], "message")
    assert "520" not in field(first[0], "message")
    assert "300" not in field(second[0], "message")

    for f in first + second:
        line = field(f, "line")
        assert isinstance(line, int) and not isinstance(line, bool)

    # No other file in the fixture is over the per-file threshold.
    other = [f for f in size3 if field(f, "file") not in (warn_file, fail_file)]
    assert other == []