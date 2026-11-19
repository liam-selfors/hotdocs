# hotdocs-criterion: sha256:a91c207f3d1ac566fec0bd5c7fe10171f61b8b286d891b8dbbaac09c2c585a6e
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _arch_doc(doc_id, title, status, depends_on=None):
    lines = [
        "---",
        "id: " + doc_id,
        "title: " + title,
        "status: " + status,
        "owners: [test-team]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000")
    if depends_on is not None:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("A test architecture document.")
    lines.append("")
    return "\n".join(lines)


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    _write(
        specs / "architecture" / "x.md",
        _arch_doc("arch-x", "X", "draft", ["arch-gone", "arch-old", "arch-ok"]),
    )
    _write(
        specs / "architecture" / "old.md",
        _arch_doc("arch-old", "Old", "deprecated"),
    )
    _write(
        specs / "architecture" / "ok.md",
        _arch_doc("arch-ok", "Ok", "draft"),
    )


def test_ac_lint_037_depends_on_missing_and_deprecated_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    target = [
        f
        for f in findings
        if field(f, "file") == "specs/architecture/x.md"
        and field(f, "rule_id") == "R-LINT-003"
        and field(f, "severity") == "fail"
    ]
    messages = [str(field(f, "message")) for f in target]

    assert len(target) == 2, messages

    gone = [m for m in messages if "arch-gone" in m]
    assert len(gone) == 1, messages
    assert "does not exist" in gone[0], messages

    old = [m for m in messages if "arch-old" in m]
    assert len(old) == 1, messages

    assert gone[0] != old[0], messages

    assert not any("arch-ok" in m for m in messages), messages