# hotdocs-criterion: sha256:e65f5cf2015d076ab08daa8a8362e22627ed770a7f8dd891f788ff82a53216b3
import io
import json
import contextlib
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_BODY = (
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small thing for testing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the small thing.\n"
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


def _build_component(repo_root, slug, extra_frontmatter_lines):
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    fm = (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
    )
    for line in extra_frontmatter_lines:
        fm += line + "\n"
    fm += "---\n"
    _write(comp_dir / "component.md", fm + COMPONENT_BODY)
    req_id = "R-" + upper + "-001"
    _write(
        comp_dir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — Foo MUST do the small thing.\n",
    )
    _write(
        comp_dir / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it does the small thing\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- None beyond defaults; measured by inspection.\n",
    )
    return comp_dir


def _build_base(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Thing** — a thing used in tests.\n",
    )
    _write(
        repo_root / "specs" / "product" / "foo-cap.md",
        "---\n"
        "id: P-FOO-CAP\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Foo capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A capability for tests.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: tests.\n"
        "\n"
        "### CS-FOO-CAP-001\n"
        "\n"
        "Covers: P-FOO-CAP\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the system\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )


def _r006_fail_findings(report, slug):
    out = []
    for f in field(report, "findings"):
        if field(f, "rule_id") != "R-LINT-006":
            continue
        if field(f, "severity") != "fail":
            continue
        file_ = str(field(f, "file")).replace("\\", "/")
        if ("components/" + slug + "/") in file_:
            out.append(f)
    return out


@pytest.mark.parametrize(
    "extra",
    [
        [],  # sealed absent, realizes absent
        ["sealed: false"],  # sealed false, realizes absent
        ["realizes: []"],  # sealed absent, empty realizes
        ["sealed: false", "realizes: []"],  # sealed false, empty realizes
    ],
)
def test_non_sealed_component_without_realizes_fails_r_lint_006(tmp_path, extra):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_base(repo_root)
    _build_component(repo_root, "foo", extra)

    report = spec_linter.lint(None, repo_root)

    matches = _r006_fail_findings(report, "foo")
    assert matches, (
        "expected a fail-severity R-LINT-006 finding for comp-foo; got "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"))
                for f in field(report, "findings")])
    )
    files = [str(field(f, "file")).replace("\\", "/") for f in matches]
    assert any(p.endswith("specs/components/foo/component.md") for p in files)
    assert field(report, "hard_failures") >= 1


def test_component_with_realizes_entry_has_no_r_lint_006(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_base(repo_root)
    _build_component(repo_root, "foo", ["sealed: false", "realizes: [P-FOO-CAP]"])

    report = spec_linter.lint(None, repo_root)

    assert _r006_fail_findings(report, "foo") == []


def test_sealed_component_without_realizes_has_no_r_lint_006(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_base(repo_root)
    _build_component(repo_root, "bar", ["sealed: true", "source_path: legacy/bar/"])

    report = spec_linter.lint(None, repo_root)

    assert _r006_fail_findings(report, "bar") == []


def test_cli_reports_r_lint_006_and_exits_1(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_base(repo_root)
    _build_component(repo_root, "foo", ["sealed: false"])

    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])

    assert code == 1
    doc = json.loads(out.getvalue())
    matches = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-006"
        and f["severity"] == "fail"
        and "components/foo/" in str(f["file"]).replace("\\", "/")
    ]
    assert matches
    assert doc["summary"]["hard_failures"] >= 1