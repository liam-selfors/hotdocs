# hotdocs-criterion: sha256:5bb371cba3a931e2d6632ed04521df38955356b0970a4ceb18ea668a97f3e336
import json
from pathlib import Path

import pytest

import spec_linter


DANGLING_ID = "comp-zz-no-such-component-anywhere"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sev(value):
    sev = field(value, "severity")
    return str(getattr(sev, "value", sev))


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root, slug, upper, depends_on):
    comp_dir = repo_root / "specs" / "components" / slug
    frontmatter = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " Component\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
    )
    body = (
        "\n# " + slug.capitalize() + "\n\n"
        + "## Purpose\n\nDoes a small thing for testing.\n\n"
        + "## Scope\n\n- In scope: testing.\n- Out of scope: everything else.\n\n"
        + "## Definitions\n\nNone.\n\n"
        + "## Behavior\n\nSee `requirements/`.\n\n"
        + "## Interfaces\n\nSee `interface/`.\n\n"
        + "## Data\n\nSee `interface/data/`.\n\n"
        + "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        + "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        + "## Open questions\n\n"
        + "## Change log\n\n- Initial draft.\n"
    )
    _write(comp_dir / "component.md", frontmatter + body)
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    _write(
        comp_dir / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** — The component MUST match existing behavior.\n",
    )
    _write(
        comp_dir / "acceptance" / (acid + ".md"),
        "# " + acid + "\n\nCovers: " + rid + "\nKind: compiled\n\n"
        + "```gherkin\nGiven the component\nWhen it runs\nThen it matches existing behavior\n```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- None beyond existing behavior.\n",
    )


def _build_corpus(repo_root, foo_depends_on):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    _component(repo_root, "foo", "FOO", foo_depends_on)
    _component(repo_root, "bar", "BAR", [])


def _r003_fails_naming(findings, ident):
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-003"
        and _sev(f) == "fail"
        and ident in str(field(f, "message"))
    ]


def test_dangling_depends_on_reports_fail_finding_naming_id(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, [DANGLING_ID])

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    matches = _r003_fails_naming(findings, DANGLING_ID)
    assert matches, (
        "expected a fail-severity R-LINT-003 finding naming "
        + repr(DANGLING_ID)
        + "; got "
        + repr(findings)
    )
    assert field(report, "hard_failures") >= 1


def test_resolvable_depends_on_has_no_r_lint_003_failure(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, ["comp-bar"])

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    bad = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-003" and _sev(f) == "fail"
    ]
    assert bad == [], repr(bad)


def test_cli_json_reports_dangling_depends_on(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, [DANGLING_ID])

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    data = json.loads(out)
    matches = _r003_fails_naming(data["findings"], DANGLING_ID)
    assert matches, repr(data)
    assert data["summary"]["hard_failures"] >= 1