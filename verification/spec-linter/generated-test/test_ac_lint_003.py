import json
from pathlib import Path

import pytest

import spec_linter


DANGLING_ID = "comp-ghost-does-not-exist"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _norm(value):
    if value is None:
        return None
    inner = getattr(value, "value", None)
    if isinstance(inner, str):
        return inner.lower()
    return str(value).lower()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id: str, title: str, depends_on: list) -> str:
    deps = "[" + ", ".join(depends_on) + "]"
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [alice]\n"
        f"depends_on: {deps}\n"
        "sealed: true\n"
        f"source_path: legacy/{comp_id}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides a small widget for test purposes.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
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


def _write_component(repo_root: Path, slug: str, prefix: str, depends_on: list) -> Path:
    base = repo_root / "specs" / "components" / slug
    comp_md = base / "component.md"
    _write(comp_md, _component_md(f"comp-{slug}", slug.capitalize(), depends_on))
    _write(
        base / "requirements" / f"R-{prefix}-001.md",
        f"# R-{prefix}-001\n\n**R-{prefix}-001** — The component MUST produce a widget.\n",
    )
    _write(
        base / "acceptance" / f"AC-{prefix}-001.md",
        f"# AC-{prefix}-001\n\n"
        f"Covers: R-{prefix}-001\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given a request\n"
        "When the component runs\n"
        "Then a widget is produced\n"
        "```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\n- Latency: under 1s, measured by timing a call.\n",
    )
    return comp_md


def _build_corpus(repo_root: Path, foo_depends_on: list) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing produced by a component.\n",
    )
    _write_component(repo_root, "bar", "BAR", [])
    _write_component(repo_root, "foo", "FOO", foo_depends_on)


def _lint_findings(repo_root: Path):
    report = spec_linter.lint(None, repo_root)
    findings = _get(report, "findings")
    assert findings is not None, "LintReport must expose findings"
    return list(findings)


def _r_lint_003(findings):
    return [f for f in findings if _norm(_get(f, "rule_id")) == "r-lint-003"]


def test_dangling_depends_on_produces_fail_finding_naming_id(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, ["comp-bar", DANGLING_ID])
    monkeypatch.chdir(repo_root)

    findings = _lint_findings(repo_root)
    r003 = _r_lint_003(findings)

    naming = [
        f for f in r003 if DANGLING_ID in str(_get(f, "message", "") or "")
    ]
    assert naming, (
        "expected an R-LINT-003 finding naming the dangling id; got: "
        + repr([(_get(f, "rule_id"), _get(f, "message")) for f in findings])
    )
    assert any(_norm(_get(f, "severity")) == "fail" for f in naming), (
        "the R-LINT-003 finding naming the dangling id must have fail severity; got "
        + repr([_get(f, "severity") for f in naming])
    )

    # The resolvable dependency must not be reported as dangling.
    for f in r003:
        msg = str(_get(f, "message", "") or "")
        assert "'comp-bar'" not in msg and '"comp-bar"' not in msg, (
            f"resolvable depends_on entry comp-bar wrongly flagged: {msg}"
        )

    report = spec_linter.lint(None, repo_root)
    hard = _get(report, "hard_failures")
    if hard is not None:
        assert hard >= 1


def test_no_dangling_finding_when_all_depends_on_resolve(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, ["comp-bar"])
    monkeypatch.chdir(repo_root)

    findings = _lint_findings(repo_root)
    r003 = _r_lint_003(findings)
    assert not r003, (
        "no R-LINT-003 finding expected when every depends_on resolves; got: "
        + repr([_get(f, "message") for f in r003])
    )


def test_cli_json_reports_dangling_depends_on_and_exits_1(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, [DANGLING_ID])
    monkeypatch.chdir(repo_root)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert code == 1, f"expected exit code 1 for a fail-severity finding, got {code}"

    try:
        data = json.loads(out)
    except ValueError:
        start = out.index("{")
        end = out.rindex("}")
        data = json.loads(out[start : end + 1])

    findings = data.get("findings", [])
    matching = [
        f
        for f in findings
        if f.get("rule_id") == "R-LINT-003"
        and f.get("severity") == "fail"
        and DANGLING_ID in str(f.get("message", ""))
    ]
    assert matching, f"expected R-LINT-003 fail finding naming {DANGLING_ID}; got {findings!r}"
    summary = data.get("summary", {})
    assert summary.get("hard_failures", 0) >= 1