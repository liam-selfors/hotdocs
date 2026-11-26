# hotdocs-criterion: sha256:2e9fb66b793905b2dab37324b43ae7a16f8529b227dc233d641fb002eae016f2
import json
from pathlib import Path

import spec_linter


GHOST_ID = "comp-ghost-dependency-xyz"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, depends_on):
    return (
        "---\n"
        + "id: " + comp_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + comp_id[len("comp-"):] + "/\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component used for testing the linter.\n"
        + "\n"
        + "## Scope\n"
        + "\n"
        + "- In scope: being a fixture.\n"
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


def _write_component(repo_root, slug, upper, depends_on):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_id = "comp-" + slug
    _write(comp_dir / "component.md", _component_md(comp_id, "Fixture " + slug, depends_on))
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        comp_dir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n"
        + "**" + req_id + "** — The fixture MUST return a value.\n",
    )
    _write(
        comp_dir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\n"
        + "Covers: " + req_id + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given a fixture\n"
        + "When it is called\n"
        + "Then it returns a value\n"
        + "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- None beyond the defaults.\n",
    )


def _base_corpus(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a thing used in tests.\n",
    )


def _findings(report):
    return list(field(report, "findings"))


def _r003_fail_naming(findings, ident):
    out = []
    for f in findings:
        if (
            field(f, "rule_id") == "R-LINT-003"
            and field(f, "severity") == "fail"
            and ident in str(field(f, "message"))
        ):
            out.append(f)
    return out


def test_dangling_depends_on_is_a_fail_finding_for_r_lint_003(tmp_path):
    repo_root = tmp_path / "repo"
    _base_corpus(repo_root)
    _write_component(repo_root, "foo", "FOO", [GHOST_ID])

    report = spec_linter.lint(None, repo_root)
    findings = _findings(report)

    matching = _r003_fail_naming(findings, GHOST_ID)
    assert matching, (
        "expected an R-LINT-003 fail finding naming " + repr(GHOST_ID)
        + "; got " + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings])
    )
    files = [str(field(f, "file")).replace("\\", "/") for f in matching]
    assert any(p.endswith("specs/components/foo/component.md") for p in files), files
    assert field(report, "hard_failures") >= 1


def test_resolving_depends_on_is_not_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    _base_corpus(repo_root)
    _write_component(repo_root, "bar", "BAR", [])
    _write_component(repo_root, "foo", "FOO", ["comp-bar"])

    report = spec_linter.lint(None, repo_root)
    findings = _findings(report)

    assert not _r003_fail_naming(findings, "comp-bar"), repr(
        [(field(f, "rule_id"), field(f, "message")) for f in findings]
    )
    assert not [f for f in findings if field(f, "rule_id") == "R-LINT-003"], repr(
        [(field(f, "rule_id"), field(f, "message")) for f in findings]
    )


def test_cli_reports_dangling_depends_on_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _base_corpus(repo_root)
    _write_component(repo_root, "foo", "FOO", [GHOST_ID])

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    matching = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-003"
        and f["severity"] == "fail"
        and GHOST_ID in f["message"]
    ]
    assert matching, repr(doc["findings"])
    assert doc["summary"]["hard_failures"] >= 1