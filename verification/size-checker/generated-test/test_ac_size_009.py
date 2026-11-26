# hotdocs-criterion: sha256:7e4d712790b4d6a8334cc154f526a4f138064b1e82a47b7af13f6d38ad952ebd
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_ac_size_009_purpose_over_warn_cap_reports_heading_line(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    ninety_words = " ".join("word" + str(i) for i in range(1, 91))
    assert len(ninety_words.split()) == 90

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
        ninety_words,
        "",
        "## Scope",
        "",
        "x.",
    ]
    assert lines[9] == "## Purpose"
    _write(
        repo_root / "specs" / "components" / "p" / "component.md",
        "\n".join(lines) + "\n",
    )

    findings = size_checker.check(repo_root)

    purpose = [f for f in findings if field(f, "rule_id") == "R-SIZE-004"]
    assert len(purpose) == 1, findings
    finding = purpose[0]

    assert field(finding, "severity") == "warn"
    line = field(finding, "line")
    assert isinstance(line, int)
    assert line == 10
    assert field(finding, "file") == "specs/components/p/component.md"

    message = field(finding, "message")
    assert "90" in message
    assert message == (
        "p: Purpose section has 90 words, above the warn threshold of 80 "
        "(specs/architecture/size-caps.md)"
    )