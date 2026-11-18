# hotdocs-criterion: sha256:62c2a8b21f3f6ebe8d5bdc55cfcd80f469e4d074f543e01fe7e9a355d088a3a9
"""AC-LINT-004: a depends_on cycle (A -> B -> A) yields a fail-severity
R-LINT-004 finding naming both components by their comp-<slug> ids."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, depends_on):
    deps = "[" + ", ".join(depends_on) + "]"
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " Component\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: " + deps + "\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + slug.capitalize() + " Component\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Matches existing behavior; do not regenerate.\n"
        + "\n"
        + "## Scope\n"
        + "\n"
        + "- In scope: existing behavior.\n"
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


def _build_component(repo_root, slug, depends_on):
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, depends_on))
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n"
        + "**" + req_id + "** — The component MUST match existing behavior.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\n"
        + "Covers: " + req_id + "\n"
        + "Kind: compiled\n\n"
        + "```gherkin\n"
        + "Given the existing behavior\n"
        + "When the component runs\n"
        + "Then it matches existing behavior\n"
        + "```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\n- None beyond existing behavior.\n",
    )


def _build_corpus(repo_root, cyclic):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    _build_component(repo_root, "alpha", ["comp-beta"])
    _build_component(repo_root, "beta", ["comp-alpha"] if cyclic else [])


def _cycle_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-004"]


def test_cycle_produces_fail_finding_naming_both_components(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, cyclic=True)

    report = spec_linter.lint(None, repo_root)

    cycle = _cycle_findings(report)
    assert cycle, "expected at least one R-LINT-004 finding for an A<->B cycle"

    naming_both = [
        f
        for f in cycle
        if field(f, "severity") == "fail"
        and "comp-alpha" in field(f, "message")
        and "comp-beta" in field(f, "message")
    ]
    assert naming_both, (
        "expected a fail-severity R-LINT-004 finding whose message names "
        "both comp-alpha and comp-beta; got: "
        + repr([(field(f, "severity"), field(f, "message")) for f in cycle])
    )
    assert field(report, "hard_failures") >= 1


def test_acyclic_dependency_produces_no_cycle_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, cyclic=False)

    report = spec_linter.lint(None, repo_root)

    assert _cycle_findings(report) == []


def test_cli_json_reports_cycle_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, cyclic=True)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    cycle = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-004"
        and f["severity"] == "fail"
        and "comp-alpha" in f["message"]
        and "comp-beta" in f["message"]
    ]
    assert cycle
    assert doc["summary"]["hard_failures"] >= 1