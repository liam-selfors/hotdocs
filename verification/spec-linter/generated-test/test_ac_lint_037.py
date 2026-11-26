# hotdocs-criterion: sha256:d397dfe2eac47232326509ca29d68548d0f6526d1172151e3b0b32a0f44696e7
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def arch_doc(doc_id, title, status, depends_on=None):
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
    lines.append("A fixture architecture document.")
    lines.append("")
    return "\n".join(lines)


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "architecture" / "x.md",
        arch_doc("arch-x", "X", "draft", ["arch-gone", "arch-old", "arch-ok"]),
    )
    write(specs / "architecture" / "old.md", arch_doc("arch-old", "Old", "deprecated"))
    write(specs / "architecture" / "ok.md", arch_doc("arch-ok", "Ok", "draft"))
    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )


def norm(p):
    return str(p).replace("\\", "/")


def test_ac_lint_037_depends_on_unresolved_and_deprecated(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    target = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-003"
        and field(f, "severity") == "fail"
        and norm(field(f, "file")) == "specs/architecture/x.md"
    ]
    messages = [str(field(f, "message")) for f in target]

    assert len(target) == 2, messages

    gone = [m for m in messages if "arch-gone" in m]
    old = [m for m in messages if "arch-old" in m]
    ok = [m for m in messages if "arch-ok" in m]

    assert len(gone) == 1, messages
    assert "does not exist" in gone[0], messages
    assert len(old) == 1, messages
    assert gone[0] != old[0], messages
    assert ok == [], messages