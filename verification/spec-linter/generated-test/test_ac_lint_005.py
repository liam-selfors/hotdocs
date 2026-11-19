# hotdocs-criterion: sha256:e5e7f939e39f3ae739e713bd43abb4e8ca74ec5286ba491dc2df7c1db168f42b
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_BODY = (
    "\n"
    "# Component\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A small fixture component used to exercise the linter.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: nothing.\n"
    "- Out of scope: everything.\n"
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    # The offending component: sealed: true with no source_path.
    write(
        specs / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "sealed: true\n"
        "---\n" + COMPONENT_BODY,
    )
    # A well-formed sealed component, for contrast.
    write(
        specs / "components" / "bar" / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "sealed: true\n"
        "source_path: legacy/bar/\n"
        "---\n" + COMPONENT_BODY,
    )


def _norm(p):
    return str(p).replace("\\", "/")


def _lint005_fail_files(findings):
    files = []
    for f in findings:
        if field(f, "rule_id") == "R-LINT-005" and field(f, "severity") == "fail":
            files.append(_norm(field(f, "file")))
    return files


def test_sealed_without_source_path_fails_r_lint_005_library(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    files = _lint005_fail_files(findings)

    assert files, "expected a fail-severity R-LINT-005 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "file")) for f in findings]
    )
    assert any(f.endswith("specs/components/foo/component.md") for f in files), files
    assert not any(f.endswith("specs/components/bar/component.md") for f in files), files
    assert field(report, "hard_failures") >= 1


def test_sealed_without_source_path_fails_r_lint_005_cli(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    report = json.loads(out)

    files = _lint005_fail_files(report["findings"])
    assert files, "expected a fail-severity R-LINT-005 finding in: " + out
    assert any(f.endswith("specs/components/foo/component.md") for f in files), files
    assert report["summary"]["hard_failures"] >= 1
    assert code == 1