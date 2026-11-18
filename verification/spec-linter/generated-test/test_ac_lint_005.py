# hotdocs-criterion: sha256:e5e7f939e39f3ae739e713bd43abb4e8ca74ec5286ba491dc2df7c1db168f42b
import json
from pathlib import Path

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _sev(finding):
    sev = _get(finding, "severity")
    sev = getattr(sev, "value", sev)
    return str(sev).strip().lower() if sev is not None else ""


def _findings(report):
    findings = _get(report, "findings")
    return list(findings or [])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(extra_frontmatter: str) -> str:
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        f"{extra_frontmatter}"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Matches existing behavior; do not regenerate.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the existing foo behavior.\n"
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


def _build_repo(repo_root: Path, extra_frontmatter: str) -> Path:
    comp_dir = repo_root / "specs" / "components" / "foo"
    component_md = comp_dir / "component.md"
    _write(component_md, _component_md(extra_frontmatter))
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST match existing behavior.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the existing foo\n"
        "When it runs\n"
        "Then it behaves as before\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    return component_md


def _lint_005(report):
    return [f for f in _findings(report) if _get(f, "rule_id") == "R-LINT-005"]


def test_sealed_true_without_source_path_fails_r_lint_005(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, "sealed: true\n")

    report = spec_linter.lint(None, repo_root)

    matches = _lint_005(report)
    assert matches, (
        "expected an R-LINT-005 finding for sealed: true with no source_path, got: "
        f"{[(_get(f, 'rule_id'), _sev(f), _get(f, 'file')) for f in _findings(report)]}"
    )
    fail_matches = [f for f in matches if _sev(f) == "fail"]
    assert fail_matches, f"R-LINT-005 finding(s) not fail-severity: {[_sev(f) for f in matches]}"

    files = [str(_get(f, "file") or "") for f in fail_matches]
    assert any("specs/components/foo/component.md" in f.replace("\\", "/") for f in files), files

    hard_failures = _get(report, "hard_failures")
    if hard_failures is None:
        summary = _get(report, "summary")
        if summary is not None:
            hard_failures = _get(summary, "hard_failures")
    if hard_failures is not None:
        assert hard_failures >= 1


def test_sealed_true_with_source_path_has_no_r_lint_005(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, "sealed: true\nsource_path: legacy/foo\n")

    report = spec_linter.lint(None, repo_root)

    fail_matches = [f for f in _lint_005(report) if _sev(f) == "fail"]
    assert not fail_matches, (
        "sealed: true with source_path must not fail R-LINT-005, got: "
        f"{[_get(f, 'message') for f in fail_matches]}"
    )


def test_cli_reports_r_lint_005_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, "sealed: true\n")

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out

    assert code == 1
    assert "R-LINT-005" in out
    start = out.find("{")
    if start != -1:
        try:
            data = json.loads(out[start:])
        except ValueError:
            data = None
        if isinstance(data, dict):
            found = [
                f
                for f in data.get("findings", [])
                if f.get("rule_id") == "R-LINT-005" and f.get("severity") == "fail"
            ]
            assert found