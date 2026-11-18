# hotdocs-criterion: sha256:c8f08b9b1081e70e298efe48bba3a8bb93f2f0f97d870a0967ad0f01fc620fd7
"""AC-LINT-035 (covers R-LINT-033): lint's findings, including those merged
in from citation-checker and size-checker, are limited to `paths`."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, missing_dep):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + slug.upper() + "\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: [" + missing_dep + "]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# Component " + slug.upper() + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component used to exercise the linter.\n"
        + "\n"
        + "## Scope\n"
        + "\n"
        + "- In scope: fixture behavior.\n"
        + "- Out of scope: everything else.\n"
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


def _build_component(repo_root, slug, missing_dep):
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, missing_dep))
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The component MUST match "
        "existing behavior.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: compiled\n\n"
        "```gherkin\nGiven the component\nWhen it runs\n"
        "Then it matches existing behavior\n```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic corpus used by tests.\n",
    )
    _build_component(repo_root, "a", "comp-does-not-exist-a")
    _build_component(repo_root, "b", "comp-does-not-exist-b")


def _norm(file_value):
    return str(file_value).replace("\\", "/")


def test_lint_findings_limited_to_directory_path(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    monkeypatch.chdir(repo_root)

    report = spec_linter.lint([Path("specs/components/a")], repo_root)
    findings = list(field(report, "findings"))

    assert findings, "expected at least one finding for component a"
    for f in findings:
        file_value = _norm(field(f, "file"))
        assert file_value.startswith("specs/components/a/"), (
            "finding outside specs/components/a/: "
            + repr(file_value) + " " + repr(field(f, "rule_id"))
        )

    assert any(
        field(f, "rule_id") == "R-LINT-003"
        and _norm(field(f, "file")) == "specs/components/a/component.md"
        for f in findings
    ), "no R-LINT-003 finding for specs/components/a/component.md: " + repr(
        [(field(f, "rule_id"), field(f, "file")) for f in findings]
    )


def test_lint_findings_limited_to_file_path(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    monkeypatch.chdir(repo_root)

    report = spec_linter.lint(
        [Path("specs/components/b/component.md")], repo_root
    )
    findings = list(field(report, "findings"))

    assert findings, "expected at least one finding for component b"
    for f in findings:
        file_value = _norm(field(f, "file"))
        assert file_value == "specs/components/b/component.md", (
            "finding outside specs/components/b/component.md: "
            + repr(file_value) + " " + repr(field(f, "rule_id"))
        )

    assert any(field(f, "rule_id") == "R-LINT-003" for f in findings), (
        "no R-LINT-003 finding among: "
        + repr([(field(f, "rule_id"), field(f, "file")) for f in findings])
    )