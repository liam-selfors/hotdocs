# hotdocs-criterion: sha256:8744ae9c6a1223ad89c07280e5aab98b74d18d2bf78dc7c4361c3a28e1d5f1b7
"""AC-SIZE-004: a 160-word Purpose section with no decision citation fails
R-SIZE-004 on length alone, naming the hard-fail threshold of 150."""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"

    purpose_words = ["alpha"] * 160
    # Spread the words over a few lines; whitespace-split count stays 160.
    purpose_lines = []
    for i in range(0, 160, 20):
        purpose_lines.append(" ".join(purpose_words[i:i + 20]))

    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "sealed: true",
        "source_path: legacy/foo/",
        "---",
        "",
        "# Foo",
        "",
        "## Purpose",
        "",
    ]
    purpose_heading_line = lines.index("## Purpose") + 1
    lines.extend(purpose_lines)
    lines.extend([
        "",
        "## Rationale",
        "",
        "Short.",
        "",
    ])
    _write(comp_dir / "component.md", "\n".join(lines))

    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST do a thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\ndo_thing() -> None\n```\n",
    )
    return purpose_heading_line


def test_ac_size_004_purpose_over_hard_fail_threshold(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    heading_line = _build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size4 = [f for f in findings if field(f, "rule_id") == "R-SIZE-004"]
    assert len(size4) == 1, findings
    finding = size4[0]

    assert field(finding, "severity") == "fail"
    assert field(finding, "file") == "specs/components/foo/component.md"
    assert field(finding, "line") == heading_line
    assert isinstance(field(finding, "line"), int)
    expected = (
        "foo: Purpose section has 160 words, above the fail threshold of 150 "
        "(specs/architecture/size-caps.md)"
    )
    assert field(finding, "message") == expected