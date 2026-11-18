# hotdocs-criterion: sha256:3ad487cc9e03cd8fe11f31166f5a260e20575e73a2f90ce387e102f53e7ae5e2
"""AC-SIZE-007: per-file word count check (R-SIZE-003) on acceptance files.

Given one acceptance file of 300 words and a second acceptance file of
520 words in the same component, when check(repo_root) runs, the first
file gets a warn R-SIZE-003 finding and the second a fail R-SIZE-003
finding, each with its own path as file and naming its own word count.
"""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _acceptance_text(total_words):
    header = "Covers: R-FOO-001\nKind: generated-test\n\n"
    header_tokens = len(header.split())
    filler_count = total_words - header_tokens
    lines = []
    words = ["word"] * filler_count
    # Wrap filler across several lines; line breaks are whitespace.
    for i in range(0, len(words), 20):
        lines.append(" ".join(words[i:i + 20]))
    text = header + "\n".join(lines) + "\n"
    assert len(text.split()) == total_words
    return text


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small thing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: a small thing.\n"
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
        "- Initial.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do a small thing.\n",
    )
    _write(comp / "acceptance" / "AC-FOO-001.md", _acceptance_text(300))
    _write(comp / "acceptance" / "AC-FOO-002.md", _acceptance_text(520))
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Thing** — a small thing.\n",
    )


def test_ac_size_007_per_file_warn_and_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    first_path = "specs/components/foo/acceptance/AC-FOO-001.md"
    second_path = "specs/components/foo/acceptance/AC-FOO-002.md"

    first = [f for f in size3 if field(f, "file") == first_path]
    second = [f for f in size3 if field(f, "file") == second_path]

    assert len(first) == 1, size3
    assert len(second) == 1, size3

    f1 = first[0]
    f2 = second[0]

    assert field(f1, "severity") == "warn"
    assert field(f2, "severity") == "fail"

    assert "300" in field(f1, "message")
    assert "520" in field(f2, "message")
    # Each names its own count, not the other's.
    assert "520" not in field(f1, "message")
    assert "300" not in field(f2, "message")

    assert isinstance(field(f1, "line"), int)
    assert isinstance(field(f2, "line"), int)

    # No other file in the fixture is over the per-file threshold.
    other = [
        f for f in size3
        if field(f, "file") not in (first_path, second_path)
    ]
    assert other == []