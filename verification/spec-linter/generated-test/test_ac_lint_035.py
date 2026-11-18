# hotdocs-criterion: sha256:c8f08b9b1081e70e298efe48bba3a8bb93f2f0f97d870a0967ad0f01fc620fd7
"""AC-LINT-035: lint limits its own and its checkers' findings to `paths`.

Covers: R-LINT-033
"""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _component_md(slug):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + slug.upper() + "\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: [comp-does-not-exist-" + slug + "]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# Component " + slug.upper() + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component used to exercise path scoping.\n"
        + "\n"
        + "## Scope\n"
        + "\n"
        + "- In scope: nothing.\n"
        + "- Out of scope: everything.\n"
        + "\n"
        + "## Definitions\n"
        + "\n"
        + "None.\n"
        + "\n"
        + "## Behavior\n"
        + "\n"
        + "See `requirements/`.\n"
        + "\n"
        + "## Interfaces\n"
        + "\n"
        + "See `interface/`.\n"
        + "\n"
        + "## Data\n"
        + "\n"
        + "See `interface/data/`.\n"
        + "\n"
        + "## Acceptance criteria\n"
        + "\n"
        + "See `acceptance/`.\n"
        + "\n"
        + "## Non-functional constraints\n"
        + "\n"
        + "See `constraints.md`.\n"
        + "\n"
        + "## Open questions\n"
        + "\n"
        + "## Change log\n"
        + "\n"
        + "- Initial draft.\n"
    )


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    (specs / "components").mkdir(parents=True)
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Fixture term** — a term used only by this test.\n",
        encoding="utf-8",
    )
    for slug in ("a", "b"):
        comp = specs / "components" / slug
        comp.mkdir(parents=True)
        (comp / "component.md").write_text(_component_md(slug), encoding="utf-8")
        (comp / "constraints.md").write_text(
            "# Constraints\n\nNone.\n", encoding="utf-8"
        )


def _rel(file_value, repo_root):
    text = str(file_value).replace("\\", "/")
    p = Path(text)
    if p.is_absolute():
        try:
            text = p.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            text = p.as_posix()
    if text.startswith("./"):
        text = text[2:]
    return text


def test_ac_lint_035_findings_limited_to_paths(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    monkeypatch.chdir(repo_root)

    # Directory path: everything must be under specs/components/a/.
    report_a = spec_linter.lint([Path("specs/components/a")], repo_root)
    findings_a = list(field(report_a, "findings"))
    files_a = [_rel(field(f, "file"), repo_root) for f in findings_a]
    for f, rel in zip(findings_a, files_a):
        assert rel.startswith("specs/components/a/"), (
            "finding outside specs/components/a/: "
            + repr((field(f, "rule_id"), rel, field(f, "message")))
        )
    assert any(
        field(f, "rule_id") == "R-LINT-003"
        and rel == "specs/components/a/component.md"
        for f, rel in zip(findings_a, files_a)
    ), "expected an R-LINT-003 finding for a/component.md, got " + repr(
        [(field(f, "rule_id"), rel) for f, rel in zip(findings_a, files_a)]
    )

    # File path: everything must be exactly specs/components/b/component.md.
    report_b = spec_linter.lint(
        [Path("specs/components/b/component.md")], repo_root
    )
    findings_b = list(field(report_b, "findings"))
    files_b = [_rel(field(f, "file"), repo_root) for f in findings_b]
    for f, rel in zip(findings_b, files_b):
        assert rel == "specs/components/b/component.md", (
            "finding outside specs/components/b/component.md: "
            + repr((field(f, "rule_id"), rel, field(f, "message")))
        )
    assert any(
        field(f, "rule_id") == "R-LINT-003" for f in findings_b
    ), "expected an R-LINT-003 finding for b/component.md, got " + repr(
        [(field(f, "rule_id"), rel) for f, rel in zip(findings_b, files_b)]
    )