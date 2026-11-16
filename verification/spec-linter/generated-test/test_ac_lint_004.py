"""AC-LINT-004 (Covers: R-LINT-004).

Given two component specs whose depends_on entries form a cycle
(A depends_on B, B depends_on A), when hotdocs lint runs against the
corpus, then the report contains a fail-severity finding for rule
R-LINT-004 naming both components.
"""

import json
from pathlib import Path

import spec_linter


ALPHA = "comp-cyc-alpha"
BETA = "comp-cyc-beta"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _component_md(comp_id, title, depends_on, source_path):
    deps = ", ".join(depends_on)
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        f"depends_on: [{deps}]\n"
        "sealed: true\n"
        f"source_path: {source_path}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small synthetic component used as a lint fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: fixture behavior.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def _write_component(repo_root, slug, comp_id, title, depends_on, prefix):
    root = repo_root / "specs" / "components" / slug
    (root / "requirements").mkdir(parents=True)
    (root / "acceptance").mkdir(parents=True)
    (root / "interface").mkdir(parents=True)
    (root / "component.md").write_text(
        _component_md(comp_id, title, depends_on, f"legacy/{slug}/"),
        encoding="utf-8",
    )
    req_id = f"R-{prefix}-001"
    ac_id = f"AC-{prefix}-001"
    (root / "requirements" / f"{req_id}.md").write_text(
        f"# {req_id}\n\n**{req_id}** — The component MUST match existing behavior.\n",
        encoding="utf-8",
    )
    (root / "acceptance" / f"{ac_id}.md").write_text(
        f"# {ac_id}\n\n"
        f"Covers: {req_id}\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given the existing behavior\n"
        "When the component runs\n"
        "Then it matches existing behavior\n"
        "```\n",
        encoding="utf-8",
    )
    (root / "constraints.md").write_text(
        "# Constraints\n\nNone beyond existing behavior.\n", encoding="utf-8"
    )


def _make_corpus(repo_root, cyclic=True):
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Fixture** — a synthetic test corpus.\n",
        encoding="utf-8",
    )
    _write_component(repo_root, "cyc-alpha", ALPHA, "Cyc Alpha", [BETA], "CYCA")
    beta_deps = [ALPHA] if cyclic else []
    _write_component(repo_root, "cyc-beta", BETA, "Cyc Beta", beta_deps, "CYCB")


def _cycle_findings(findings):
    out = []
    for f in findings:
        if field(f, "rule_id") != "R-LINT-004":
            continue
        out.append(f)
    return out


def _names_both(f):
    msg = str(field(f, "message"))
    return ALPHA in msg and BETA in msg


def test_cycle_reported_as_fail_naming_both_components(tmp_path):
    repo_root = tmp_path / "repo"
    _make_corpus(repo_root, cyclic=True)

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    cycle = _cycle_findings(findings)

    assert cycle, (
        "expected an R-LINT-004 finding for the depends_on cycle; got: "
        + repr([(field(f, "rule_id"), field(f, "message")) for f in findings])
    )
    matching = [
        f for f in cycle if field(f, "severity") == "fail" and _names_both(f)
    ]
    assert matching, (
        "expected a fail-severity R-LINT-004 finding naming both "
        f"{ALPHA} and {BETA}; got: "
        + repr(
            [(field(f, "severity"), field(f, "message")) for f in cycle]
        )
    )

    hard = (
        report["hard_failures"]
        if isinstance(report, dict)
        else report.hard_failures
    )
    assert hard >= 1


def test_acyclic_corpus_has_no_cycle_finding(tmp_path):
    repo_root = tmp_path / "repo"
    _make_corpus(repo_root, cyclic=False)

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    cycle = _cycle_findings(findings)
    assert not [f for f in cycle if field(f, "severity") == "fail"], repr(
        [field(f, "message") for f in cycle]
    )


def test_cli_reports_cycle_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _make_corpus(repo_root, cyclic=True)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert code == 1

    data = json.loads(out)
    findings = data["findings"]
    matching = [
        f
        for f in findings
        if f["rule_id"] == "R-LINT-004"
        and f["severity"] == "fail"
        and ALPHA in f["message"]
        and BETA in f["message"]
    ]
    assert matching, repr(findings)
    assert data["summary"]["hard_failures"] >= 1