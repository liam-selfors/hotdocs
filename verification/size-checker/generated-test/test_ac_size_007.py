# hotdocs-criterion: sha256:4a144481c9792ffe662b1d5e965646e8025271745b9bc3d4748df446390d01c4
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def acceptance_text(ac_id, req_id, total_words):
    head = "# " + ac_id + "\n\nCovers: " + req_id + "\n\n"
    head_words = len(head.split())
    filler_count = total_words - head_words
    lines = []
    chunk = []
    for i in range(filler_count):
        chunk.append("word")
        if len(chunk) == 12:
            lines.append(" ".join(chunk))
            chunk = []
    if chunk:
        lines.append(" ".join(chunk))
    text = head + "\n".join(lines) + "\n"
    assert len(text.split()) == total_words
    return text


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used for size checks.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST do one thing.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — The component MUST do another thing.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        acceptance_text("AC-FOO-001", "R-FOO-001", 300),
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        acceptance_text("AC-FOO-002", "R-FOO-002", 520),
    )


def test_ac_size_007_per_file_warn_and_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    first = "specs/components/foo/acceptance/AC-FOO-001.md"
    second = "specs/components/foo/acceptance/AC-FOO-002.md"

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    first_findings = [f for f in size3 if field(f, "file") == first]
    second_findings = [f for f in size3 if field(f, "file") == second]

    assert len(first_findings) == 1, size3
    assert len(second_findings) == 1, size3

    f1 = first_findings[0]
    assert field(f1, "severity") == "warn"
    assert isinstance(field(f1, "line"), int)
    assert "300" in field(f1, "message")
    assert field(f1, "message") == (
        first + " has 300 words, above the per-file warn threshold of 250"
    )

    f2 = second_findings[0]
    assert field(f2, "severity") == "fail"
    assert isinstance(field(f2, "line"), int)
    assert "520" in field(f2, "message")
    assert field(f2, "message") == (
        second + " has 520 words, above the per-file fail threshold of 500"
    )