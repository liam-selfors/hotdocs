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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Example term** — a placeholder glossary entry for this fixture.\n",
    )
    _write(
        specs / "architecture" / "x.md",
        "---\n"
        "id: arch-x\n"
        "title: Architecture X\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: [arch-gone, arch-old, arch-ok]\n"
        "---\n"
        "\n"
        "# Architecture X\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture architecture document with three dependencies.\n",
    )
    _write(
        specs / "architecture" / "old.md",
        "---\n"
        "id: arch-old\n"
        "title: Architecture Old\n"
        "status: deprecated\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Architecture Old\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A deprecated fixture architecture document.\n",
    )
    _write(
        specs / "architecture" / "ok.md",
        "---\n"
        "id: arch-ok\n"
        "title: Architecture OK\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Architecture OK\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A draft fixture architecture document.\n",
    )


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def test_ac_lint_037_dangling_and_deprecated_depends_on(tmp_path):
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
        and _norm(field(f, "file")) == "specs/architecture/x.md"
    ]

    messages = [str(field(f, "message")) for f in target]
    assert len(target) == 2, messages

    gone = [m for m in messages if "arch-gone" in m]
    old = [m for m in messages if "arch-old" in m]
    ok = [m for m in messages if "arch-ok" in m]

    assert len(gone) == 1, messages
    assert "does not exist" in gone[0], gone[0]
    assert len(old) == 1, messages
    assert gone[0] != old[0], messages
    assert ok == [], messages

    # And no R-LINT-003 finding of any severity on x.md names arch-ok.
    for f in findings:
        if (
            field(f, "rule_id") == "R-LINT-003"
            and _norm(field(f, "file")) == "specs/architecture/x.md"
        ):
            assert "arch-ok" not in str(field(f, "message"))