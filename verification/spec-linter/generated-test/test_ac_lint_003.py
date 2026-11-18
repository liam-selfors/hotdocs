# hotdocs-criterion: sha256:5bb371cba3a931e2d6632ed04521df38955356b0970a4ceb18ea668a97f3e336
import json
from pathlib import Path

import spec_linter


DANGLING_ID = "comp-ghost-dep"
PRESENT_ID = "comp-present-dep"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _norm(value):
    return str(getattr(value, "value", value))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id: str, title: str, depends_on: list, source_path: str) -> str:
    deps = "[" + ", ".join(depends_on) + "]"
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        f"depends_on: {deps}\n"
        "sealed: true\n"
        f"source_path: {source_path}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides a small synthetic behavior used only as a lint fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the synthetic behavior.\n"
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


def _make_component(repo_root: Path, slug: str, prefix: str, depends_on: list) -> None:
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        _component_md(f"comp-{slug}", f"Synthetic {slug}", depends_on, f"legacy/{slug}/"),
    )
    req_id = f"R-{prefix}-001"
    ac_id = f"AC-{prefix}-001"
    _write(
        base / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\n**{req_id}** — The component MUST return the value it is given.\n",
    )
    _write(
        base / "acceptance" / f"{ac_id}.md",
        f"# {ac_id}\n\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a value 1\n"
        "When the component runs\n"
        "Then it returns 1\n"
        "```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\n- Runs in under 1 second, measured by wall clock.\n",
    )
    (repo_root / "legacy" / slug).mkdir(parents=True, exist_ok=True)


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a synthetic fixture term.\n",
    )
    # A dependency that does exist.
    _make_component(repo_root, "present-dep", "PRESENTDEP", [])
    # The component under lint: one resolvable dependency, one dangling one.
    _make_component(repo_root, "foo", "FOO", [PRESENT_ID, DANGLING_ID])


def _lint003_findings(findings):
    return [f for f in findings if _norm(field(f, "rule_id")) == "R-LINT-003"]


def test_dangling_depends_on_yields_fail_finding_naming_id(tmp_path):
    _build_fixture(tmp_path)

    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))

    lint003 = _lint003_findings(findings)
    matching = [
        f
        for f in lint003
        if _norm(field(f, "severity")) == "fail" and DANGLING_ID in str(field(f, "message"))
    ]
    assert matching, (
        "expected a fail-severity R-LINT-003 finding naming "
        f"{DANGLING_ID!r}; got: {[(field(f, 'rule_id'), field(f, 'severity'), field(f, 'message')) for f in findings]}"
    )

    # The resolvable dependency must not be reported as dangling.
    assert not any(PRESENT_ID in str(field(f, "message")) for f in lint003), (
        f"resolvable dependency {PRESENT_ID!r} was wrongly reported by R-LINT-003"
    )

    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_dangling_depends_on_via_cli_json(tmp_path, capsys):
    _build_fixture(tmp_path)

    code = spec_linter.main([f"--repo-root={tmp_path}", "--format=json"])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    findings = doc["findings"]
    matching = [
        f
        for f in findings
        if f["rule_id"] == "R-LINT-003"
        and f["severity"] == "fail"
        and DANGLING_ID in f["message"]
    ]
    assert matching, f"no fail R-LINT-003 finding naming {DANGLING_ID!r} in {findings}"
    assert doc["summary"]["hard_failures"] >= 1