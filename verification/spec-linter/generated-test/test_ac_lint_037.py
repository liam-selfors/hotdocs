# hotdocs-criterion: sha256:a91c207f3d1ac566fec0bd5c7fe10171f61b8b286d891b8dbbaac09c2c585a6e
"""AC-LINT-037 (covers R-LINT-003).

Given specs/architecture/x.md with id arch-x and depends_on
  [arch-gone, arch-old, arch-ok], where no spec has id arch-gone,
  arch-old's status is deprecated and arch-ok's is draft
When lint(None, repo_root) runs
Then specs/architecture/x.md has exactly two R-LINT-003 fail findings,
  one naming arch-gone with "does not exist" in its message and one
  naming arch-old, and none naming arch-ok
"""

from pathlib import Path

import spec_linter


TARGET_FILE = "specs/architecture/x.md"


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
    lines.append("## Change log")
    lines.append("")
    lines.append("- Initial draft.")
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


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def _is_target_file(path_value, repo_root):
    p = _norm(path_value)
    if p == TARGET_FILE:
        return True
    root = _norm(Path(repo_root).resolve())
    if p.startswith(root + "/") and p[len(root) + 1:] == TARGET_FILE:
        return True
    return p.endswith("/" + TARGET_FILE)


def test_ac_lint_037_unresolved_and_deprecated_depends_on_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    target = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-003"
        and field(f, "severity") == "fail"
        and _is_target_file(field(f, "file"), repo_root)
    ]
    messages = [str(field(f, "message")) for f in target]

    assert len(target) == 2, (
        "expected exactly two R-LINT-003 fail findings on "
        + TARGET_FILE
        + ", got: "
        + repr(messages)
        + " (all findings: "
        + repr([(field(f, "rule_id"), field(f, "severity"), _norm(field(f, "file")), field(f, "message")) for f in findings])
        + ")"
    )

    gone = [m for m in messages if "arch-gone" in m]
    old = [m for m in messages if "arch-old" in m]
    ok = [m for m in messages if "arch-ok" in m]

    assert len(gone) == 1, "expected one finding naming arch-gone: " + repr(messages)
    assert "does not exist" in gone[0], (
        "arch-gone finding should say 'does not exist': " + repr(gone[0])
    )
    assert len(old) == 1, "expected one finding naming arch-old: " + repr(messages)
    assert gone[0] != old[0], "arch-gone and arch-old must be separate findings: " + repr(messages)
    assert ok == [], "no finding should name arch-ok: " + repr(ok)