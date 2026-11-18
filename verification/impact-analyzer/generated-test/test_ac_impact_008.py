# hotdocs-criterion: sha256:867fe269983858c3e59a96d389d8b34fa99ddd0869dfecd186def610b9e1e99c
"""AC-IMPACT-008 (covers R-IMPACT-008).

Given comp-foo's interface/guarantees/G-FOO-001.md changed, and comp-bar
depends_on comp-foo with no depends_on_guarantees declared for comp-foo,
when the blast radius for --changed comp-foo is computed, the report's
impacted list contains comp-bar with reason "transitive-guarantee" and
via "comp-foo" (the coarse, safe default).
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import impact_analyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root: Path, *args: str) -> None:
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    cmd = [
        "git",
        "-c", "user.name=Test Author",
        "-c", "user.email=test-author@example.invalid",
        "-c", "commit.gpgsign=false",
        "-c", "core.hooksPath=/dev/null",
        "-c", "init.defaultBranch=main",
        *args,
    ]
    result = subprocess.run(
        cmd, cwd=str(repo_root), env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed: {result.stdout}\n{result.stderr}"
    )


def _component_md(comp_id: str, title: str, purpose: str, extra_frontmatter: str) -> str:
    slug = comp_id[len("comp-"):]
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        f"{extra_frontmatter}"
        "sealed: true\n"
        f"source_path: legacy/{slug}\n"
        "---\n"
        "\n"
        f"# {comp_id}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose}\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"{title} exists so its callers have one stable place for this behavior.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"- In scope: the behavior stated in {title}'s requirements.\n"
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


def _requirement(req_id: str, statement: str) -> str:
    return f"# {req_id}\n\n**{req_id}** — {statement}\n"


def _acceptance(ac_id: str, req_id: str, given: str, when: str, then: str) -> str:
    return (
        f"# {ac_id}\n"
        "\n"
        f"Covers: {req_id}\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        f"Given {given}\n"
        f"When {when}\n"
        f"Then {then}\n"
        "```\n"
    )


def _constraints(name: str) -> str:
    return (
        "# Constraints\n"
        "\n"
        f"- Latency: each {name} call MUST complete within 100 ms, measured by "
        "timing a single call in a test.\n"
    )


G_FOO_001_V1 = "# G-FOO-001\n\ncomp-foo MUST return its results in sorted order.\n"
G_FOO_001_V2 = "# G-FOO-001\n\ncomp-foo MUST return its results in ascending sorted order.\n"
G_FOO_001_V3 = (
    "# G-FOO-001\n\ncomp-foo MUST return its results in ascending lexicographic order.\n"
)
G_FOO_002 = "# G-FOO-002\n\ncomp-foo MUST NOT return duplicate results.\n"


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this fixture corpus.\n"
        "\n"
        "- **Result** — a single string a component returns to its caller.\n",
    )

    # comp-foo: upstream, owns two guarantees.
    foo = specs / "components" / "foo"
    _write(
        foo / "component.md",
        _component_md(
            "comp-foo",
            "Foo",
            "Foo returns sorted, de-duplicated results to its callers.",
            "",
        ),
    )
    _write(
        foo / "requirements" / "R-FOO-001.md",
        _requirement("R-FOO-001", "comp-foo MUST return its results in sorted order."),
    )
    _write(
        foo / "acceptance" / "AC-FOO-001.md",
        _acceptance(
            "AC-FOO-001",
            "R-FOO-001",
            "an unsorted input list",
            "comp-foo is called",
            "the returned results are sorted",
        ),
    )
    _write(
        foo / "interface" / "data" / "FooResult.md",
        "# `FooResult`\n\nA list of strings, sorted ascending.\n",
    )
    _write(foo / "interface" / "guarantees" / "G-FOO-001.md", G_FOO_001_V1)
    _write(foo / "interface" / "guarantees" / "G-FOO-002.md", G_FOO_002)
    _write(foo / "constraints.md", _constraints("comp-foo"))

    # comp-bar: depends_on comp-foo, declares NO depends_on_guarantees.
    bar = specs / "components" / "bar"
    _write(
        bar / "component.md",
        _component_md(
            "comp-bar",
            "Bar",
            "Bar formats the results it obtains from Foo for display.",
            "depends_on: [comp-foo]\n",
        ),
    )
    _write(
        bar / "requirements" / "R-BAR-001.md",
        _requirement("R-BAR-001", "comp-bar MUST format each result on its own line."),
    )
    _write(
        bar / "acceptance" / "AC-BAR-001.md",
        _acceptance(
            "AC-BAR-001",
            "R-BAR-001",
            "two results",
            "comp-bar formats them",
            "the output has two lines",
        ),
    )
    _write(
        bar / "interface" / "data" / "BarOutput.md",
        "# `BarOutput`\n\nA string with one result per line.\n",
    )
    _write(bar / "constraints.md", _constraints("comp-bar"))

    # Sealed components' hand-maintained source, never under gen/.
    _write(repo_root / "legacy" / "foo" / "foo.py", "VALUE = 1\n")
    _write(repo_root / "legacy" / "bar" / "bar.py", "VALUE = 2\n")


def _find_tool_module(slug: str, module_name: str):
    """Locate the tool's own copy of a dependency next to impact_analyzer."""
    start = Path(impact_analyzer.__file__).resolve()
    for parent in start.parents:
        flat = parent / "gen" / slug / f"{module_name}.py"
        if flat.is_file():
            return flat, False
        pkg = parent / "gen" / slug / module_name / "__init__.py"
        if pkg.is_file():
            return pkg, True
    return None, False


def _load_spec_linter():
    path, is_pkg = _find_tool_module("spec-linter", "spec_linter")
    if path is None:
        return None
    module_name = "spec_linter"
    if is_pkg:
        spec = importlib.util.spec_from_file_location(
            module_name, path, submodule_search_locations=[str(path.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


def _fail_findings(report):
    findings = _get(report, "findings", []) or []
    return [f for f in findings if _get(f, "severity") == "fail"]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_root(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to construct a prior-commit fixture")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _build_corpus(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial corpus")

    # Change ONLY G-FOO-001, committed, and change it again in the working
    # tree, so that it differs from the prior commit however "prior" is read
    # (HEAD~1 vs HEAD, HEAD vs working tree, or HEAD~1 vs working tree).
    guarantee = root / "specs" / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md"
    guarantee.write_text(G_FOO_001_V2, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "change G-FOO-001")
    guarantee.write_text(G_FOO_001_V3, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_ac_impact_008_dependent_without_declared_guarantees_gets_coarse_default(repo_root):
    # Precondition (R-IMPACT-007): the fixture corpus must lint clean.
    linter = _load_spec_linter()
    if linter is not None:
        lint_report = linter.lint(None, repo_root)
        failures = _fail_findings(lint_report)
        messages = [
            f"{_get(f, 'rule_id')} {_get(f, 'file')}:{_get(f, 'line')} {_get(f, 'message')}"
            for f in failures
        ]
        assert not failures, "fixture corpus is not lint-clean:\n" + "\n".join(messages)

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo_root)

    precondition_error = _get(report, "precondition_error")
    assert precondition_error is None, f"unexpected precondition error: {precondition_error!r}"

    impacted = list(_get(report, "impacted", []) or [])
    by_id = {}
    for entry in impacted:
        comp_id = _get(entry, "component_id")
        assert comp_id not in by_id, f"{comp_id} appears more than once in impacted"
        by_id[comp_id] = entry

    # The changed component itself is always direct.
    assert "comp-foo" in by_id, f"comp-foo missing from impacted: {impacted!r}"
    assert _get(by_id["comp-foo"], "reason") == "direct"
    assert _get(by_id["comp-foo"], "via") is None

    # The dependent with no depends_on_guarantees is included unconditionally.
    assert "comp-bar" in by_id, (
        f"comp-bar (depends_on comp-foo, no depends_on_guarantees) missing: {impacted!r}"
    )
    bar = by_id["comp-bar"]
    assert _get(bar, "reason") == "transitive-guarantee"
    assert _get(bar, "via") == "comp-foo"

    # Coarse default: guarantee_ids lists every guarantee file that changed —
    # here exactly G-FOO-001, never the unchanged G-FOO-002.
    guarantee_ids = _get(bar, "guarantee_ids")
    assert guarantee_ids is not None, "transitive-guarantee entry must carry guarantee_ids"
    assert sorted(guarantee_ids) == ["G-FOO-001"]

    # Never the bare slug form.
    assert "bar" not in by_id
    assert "foo" not in by_id