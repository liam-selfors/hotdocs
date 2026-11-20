# hotdocs-criterion: sha256:b33a5ab14e82c35a4d4f711beba8b5f6d5d889eb65581c9db94f878742ea48a8
import io
import json
import contextlib
from pathlib import Path

import spec_linter


DANGLING_ID = "comp-nonexistent-dangling-target"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n"
        "- **Widget** — a small thing used only by this test fixture.\n",
    )

    comp_dir = specs / "components" / "foo"
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: [" + DANGLING_ID + "]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does one small thing for this fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the one small thing.\n"
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
    _write(comp_dir / "component.md", component_md)
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n"
        "**R-FOO-001** — The component MUST match existing behavior.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given the existing behavior\n"
        "When foo runs\n"
        "Then the behavior is unchanged\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone.\n",
    )


def _matching_findings(findings):
    out = []
    for f in findings:
        if (
            field(f, "rule_id") == "R-LINT-003"
            and field(f, "severity") == "fail"
            and DANGLING_ID in str(field(f, "message"))
        ):
            out.append(f)
    return out


def test_dangling_depends_on_is_r_lint_003_fail_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    # Sanity: the dangling id has no spec file anywhere under specs/.
    for p in (repo_root / "specs").rglob("*.md"):
        assert p.stem != DANGLING_ID

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    matches = _matching_findings(findings)
    assert matches, (
        "expected a fail-severity R-LINT-003 finding naming "
        + repr(DANGLING_ID)
        + "; got "
        + repr(
            [
                (field(f, "rule_id"), field(f, "severity"), field(f, "message"))
                for f in findings
            ]
        )
    )
    assert field(report, "hard_failures") >= 1


def test_cli_json_report_contains_dangling_depends_on_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])

    assert code == 1, "stderr: " + err.getvalue()
    doc = json.loads(out.getvalue())
    matches = _matching_findings(doc["findings"])
    assert matches, "findings: " + repr(doc["findings"])
    assert doc["summary"]["hard_failures"] >= 1