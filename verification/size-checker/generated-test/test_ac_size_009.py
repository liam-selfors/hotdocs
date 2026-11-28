# hotdocs-criterion: sha256:85b7ea46aacc667bcdf070b0a629287296c3c094a5f321c01debb4c1ff3ae4b7
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fixture(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "p"
    comp_dir.mkdir(parents=True)
    words = " ".join("w" + str(i) for i in range(90))
    assert len(words.split()) == 90
    lines = [
        "---",
        "id: comp-p",
        "title: P",
        "status: draft",
        "owners: [t]",
        "---",
        "",
        "# P",
        "",
        "## Purpose",
        "",
        words,
        "",
        "## Scope",
        "",
        "x.",
    ]
    assert lines[9] == "## Purpose"
    (comp_dir / "component.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_ac_size_009_purpose_over_warn_reports_heading_line(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    findings = size_checker.check(repo_root)

    purpose = [f for f in findings if field(f, "rule_id") == "R-SIZE-004"]
    assert len(purpose) == 1, findings
    finding = purpose[0]

    assert field(finding, "severity") == "warn"
    assert field(finding, "line") == 10
    assert isinstance(field(finding, "line"), int)
    assert field(finding, "file") == "specs/components/p/component.md"

    message = field(finding, "message")
    assert "90" in message
    assert message == (
        "p: Purpose section has "
        + "90"
        + " words, above the warn threshold of "
        + "80"
        + " (specs/architecture/size-caps.md)"
    )