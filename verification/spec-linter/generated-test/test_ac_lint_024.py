import json
from pathlib import Path

import spec_linter


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str, purpose: str, rationale: str | None) -> str:
    parts = [
        "---",
        f"id: comp-{slug}",
        f"title: {slug.capitalize()} Formatter",
        "status: draft",
        "owners: [alice]",
        "sealed: true",
        f"source_path: legacy/{slug}",
        "---",
        "",
        f"# {slug.capitalize()} Formatter",
        "",
        "## Purpose",
        "",
        purpose,
        "",
    ]
    if rationale is not None:
        parts += ["## Rationale", "", rationale, ""]
    parts += [
        "## Scope",
        "",
        f"- In scope: formatting {slug} records.",
        "- Out of scope: parsing.",
        "",
        "## Definitions",
        "",
        "None.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "## Change log",
        "",
        "- Initial draft.",
        "",
    ]
    return "\n".join(parts)


def _make_component(repo: Path, slug: str, purpose: str, rationale: str | None) -> None:
    upper = slug.upper()
    base = repo / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, purpose, rationale))
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The formatter MUST return a "
        f"non-empty string for every {slug} record.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: compiled\n\n"
        "```gherkin\nGiven a record\nWhen it is formatted\n"
        "Then the result is a non-empty string\n```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\n- Formatting one record MUST take under 10 ms, "
        "measured by a benchmark.\n",
    )


def _write_decision(repo: Path) -> None:
    _write(
        repo / "specs" / "decisions" / "D30.md",
        "---\nid: D30\ntitle: Split parsing from formatting\nstatus: draft\n"
        "owners: [alice]\n---\n\n# D30\n\nParsing and formatting were "
        "coupled; split them.\n",
    )


def _write_glossary(repo: Path) -> None:
    _write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Record** — one input item.\n",
    )


CITING_PURPOSE = (
    "Formats widget records for display. This unit was extracted once "
    "D30 found a real coupling between parsing and formatting."
)
CLEAN_PURPOSE = "Formats gadget records for display."
MOVED_RATIONALE = (
    "This unit was extracted once D30 found a real coupling between "
    "parsing and formatting."
)


def _lint024(report):
    findings = _get(report, "findings") or []
    return [f for f in findings if _get(f, "rule_id") == "R-LINT-024"]


def _norm(p) -> str:
    return str(p or "").replace("\\", "/")


def _build_two_component_repo(repo: Path) -> None:
    _write_glossary(repo)
    _write_decision(repo)
    _make_component(repo, "alpha", CITING_PURPOSE, None)
    _make_component(repo, "beta", CLEAN_PURPOSE, MOVED_RATIONALE)


def test_purpose_citation_fails_and_rationale_citation_does_not(tmp_path):
    repo = tmp_path / "repo"
    _build_two_component_repo(repo)

    report = spec_linter.lint(None, repo)
    hits = _lint024(report)

    alpha_hits = [
        f for f in hits
        if _norm(_get(f, "file")).endswith("specs/components/alpha/component.md")
    ]
    assert alpha_hits, f"expected an R-LINT-024 finding on alpha's component.md, got {hits!r}"
    for f in alpha_hits:
        assert _get(f, "severity") == "fail"

    beta_hits = [
        f for f in hits
        if "specs/components/beta/" in _norm(_get(f, "file"))
    ]
    assert beta_hits == [], f"beta's Purpose has no citation, yet got {beta_hits!r}"

    hard = _get(report, "hard_failures")
    assert hard is not None and hard >= 1


def test_component_with_citation_only_in_rationale_has_no_finding(tmp_path):
    repo = tmp_path / "repo"
    _write_glossary(repo)
    _write_decision(repo)
    _make_component(repo, "beta", CLEAN_PURPOSE, MOVED_RATIONALE)

    report = spec_linter.lint(None, repo)
    assert _lint024(report) == []


def test_backtick_wrapped_citation_in_purpose_also_fails(tmp_path):
    repo = tmp_path / "repo"
    _write_glossary(repo)
    _write_decision(repo)
    _make_component(
        repo,
        "gamma",
        "Formats gamma records for display. This unit was extracted once "
        "`D30` found a real coupling between parsing and formatting.",
        None,
    )

    report = spec_linter.lint(None, repo)
    hits = [
        f for f in _lint024(report)
        if _norm(_get(f, "file")).endswith("specs/components/gamma/component.md")
    ]
    assert hits
    assert all(_get(f, "severity") == "fail" for f in hits)


def test_cli_reports_r_lint_024_and_exits_1(tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    _build_two_component_repo(repo)
    monkeypatch.chdir(repo)

    code = spec_linter.main(["--format=json", f"--repo-root={repo}"])
    out = capsys.readouterr().out
    assert code == 1

    data = json.loads(out.strip())
    findings = data.get("findings", [])
    rule_hits = [f for f in findings if f.get("rule_id") == "R-LINT-024"]
    assert any(
        _norm(f.get("file")).endswith("specs/components/alpha/component.md")
        and f.get("severity") == "fail"
        for f in rule_hits
    )
    assert not any(
        "specs/components/beta/" in _norm(f.get("file")) for f in rule_hits
    )