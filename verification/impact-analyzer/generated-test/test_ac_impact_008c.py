"""AC-IMPACT-008c (covers R-IMPACT-008).

Given comp-foo has two guarantees, G-FOO-001 and G-FOO-002; comp-bar
depends_on comp-foo and declares depends_on_guarantees: [G-FOO-001] only;
and this commit changes G-FOO-001,
When hotdocs impact --changed comp-foo runs,
Then the report's impacted list contains comp-bar with reason
"transitive-guarantee" naming G-FOO-001.
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
# Generic helpers
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
    env.update(
        {
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
    )
    subprocess.run(
        [
            "git",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


# ---------------------------------------------------------------------------
# Locating spec-linter's real lint() (dynamic, never statically importable)
# ---------------------------------------------------------------------------


def _load_module_from_file(module_name: str, module_path: Path, package_dir=None):
    if package_dir is not None:
        spec = importlib.util.spec_from_file_location(
            module_name, module_path, submodule_search_locations=[str(package_dir)]
        )
    else:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


def _find_lint():
    module_name = "spec_linter"
    candidates = []
    try:
        start = Path(impact_analyzer.__file__).resolve().parent
        candidates.extend([start, *start.parents])
    except Exception:
        pass
    try:
        cwd = Path.cwd().resolve()
        candidates.extend([cwd, *cwd.parents])
    except Exception:
        pass
    seen = set()
    for root in candidates:
        if root in seen:
            continue
        seen.add(root)
        base = root / "gen" / "spec-linter"
        flat = base / f"{module_name}.py"
        pkg = base / module_name / "__init__.py"
        try:
            if flat.is_file():
                mod = _load_module_from_file(module_name, flat)
                return getattr(mod, "lint", None)
            if pkg.is_file():
                mod = _load_module_from_file(module_name, pkg, package_dir=pkg.parent)
                return getattr(mod, "lint", None)
        except Exception:
            continue
    return None


def _hard_failures(report):
    findings = _get(report, "findings", []) or []
    fails = [f for f in findings if _get(f, "severity") == "fail"]
    count = _get(report, "hard_failures", None)
    if count is None:
        summary = _get(report, "summary", None)
        if summary is not None:
            count = _get(summary, "hard_failures", None)
    if count is None:
        count = len(fails)
    return count, fails


# ---------------------------------------------------------------------------
# Synthetic, lint-clean fixture corpus
# ---------------------------------------------------------------------------


def _component_md(comp_id, title, source_path, extra_frontmatter=""):
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        f"{extra_frontmatter}"
        "sealed: true\n"
        f"source_path: {source_path}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{title} is a small fixture component used only by this test corpus.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the single fixture behavior described in requirements.\n"
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
        "None.\n"
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
        "- Initial fixture.\n"
    )


def _requirement(rid, text):
    return f"# {rid}\n\n**{rid}** — {text}\n"


def _acceptance(acid, rid):
    return (
        f"# {acid}\n"
        "\n"
        f"Covers: {rid}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a fixture input\n"
        "When the fixture runs\n"
        "Then it returns the input unchanged\n"
        "```\n"
    )


def _constraints():
    return (
        "# Constraints\n"
        "\n"
        "- Latency: one fixture call MUST complete within 1 second, measured "
        "by timing a single call.\n"
    )


def _guarantee(gid, text):
    return f"# {gid}\n\n{text}\n"


G1_V1 = "The foo fixture MUST return results in a stable order."
G1_V2 = "The foo fixture MUST return results in a stable, ascending order."
G1_V3 = "The foo fixture MUST return results in a stable, ascending lexical order."
G2 = "The foo fixture MUST NOT mutate its input."


def _build_corpus(repo_root: Path, g1_text: str) -> None:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test-only spec corpus.\n",
    )

    foo = specs / "components" / "foo"
    _write(foo / "component.md", _component_md("comp-foo", "Foo", "legacy/foo"))
    _write(
        foo / "requirements" / "R-FOO-001.md",
        _requirement("R-FOO-001", "The foo fixture MUST return its input unchanged."),
    )
    _write(foo / "acceptance" / "AC-FOO-001.md", _acceptance("AC-FOO-001", "R-FOO-001"))
    _write(foo / "constraints.md", _constraints())
    _write(foo / "interface" / "guarantees" / "G-FOO-001.md", _guarantee("G-FOO-001", g1_text))
    _write(foo / "interface" / "guarantees" / "G-FOO-002.md", _guarantee("G-FOO-002", G2))

    bar = specs / "components" / "bar"
    _write(
        bar / "component.md",
        _component_md(
            "comp-bar",
            "Bar",
            "legacy/bar",
            extra_frontmatter="depends_on: [comp-foo]\ndepends_on_guarantees: [G-FOO-001]\n",
        ),
    )
    _write(
        bar / "requirements" / "R-BAR-001.md",
        _requirement("R-BAR-001", "The bar fixture MUST return its input unchanged."),
    )
    _write(bar / "acceptance" / "AC-BAR-001.md", _acceptance("AC-BAR-001", "R-BAR-001"))
    _write(bar / "constraints.md", _constraints())

    _write(repo_root / "legacy" / "foo" / "foo.py", "def run(x):\n    return x\n")
    _write(repo_root / "legacy" / "bar" / "bar.py", "def run(x):\n    return x\n")


@pytest.fixture
def repo_root(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to construct a prior-commit fixture")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")

    # Prior commit: original G-FOO-001.
    _build_corpus(root, G1_V1)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "prior")

    # This commit: G-FOO-001 changed, G-FOO-002 untouched.
    _write(
        root / "specs" / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        _guarantee("G-FOO-001", G1_V2),
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "change G-FOO-001")

    # Also leave G-FOO-001 (only) differing in the working tree, so the
    # change is visible whether "prior commit" is compared against HEAD or
    # HEAD~1. G-FOO-002 is identical in every state.
    _write(
        root / "specs" / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        _guarantee("G-FOO-001", G1_V3),
    )
    return root


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------


def test_narrowed_dependent_included_when_its_declared_guarantee_changes(repo_root):
    lint = _find_lint()
    if lint is not None:
        lint_report = lint(None, repo_root)
        count, fails = _hard_failures(lint_report)
        details = "\n".join(
            f"{_get(f, 'rule_id')} {_get(f, 'file')}:{_get(f, 'line')} {_get(f, 'message')}"
            for f in fails
        )
        assert count == 0, f"fixture corpus is not lint-clean:\n{details}"

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo_root)

    precondition_error = _get(report, "precondition_error")
    assert precondition_error is None, (
        f"unexpected precondition error: {precondition_error!r}"
    )

    impacted = list(_get(report, "impacted", []) or [])
    by_id = {}
    for entry in impacted:
        cid = _get(entry, "component_id")
        assert cid not in by_id, f"{cid} appears more than once in impacted"
        by_id[cid] = entry

    # The changed component itself is direct.
    assert "comp-foo" in by_id, f"comp-foo missing from impacted: {impacted!r}"
    assert _get(by_id["comp-foo"], "reason") == "direct"

    # Narrowing must not exclude comp-bar from a change it declared reliance on.
    assert "comp-bar" in by_id, (
        f"comp-bar missing from impacted despite G-FOO-001 changing: {impacted!r}"
    )
    bar = by_id["comp-bar"]
    assert _get(bar, "reason") == "transitive-guarantee", (
        f"unexpected reason for comp-bar: {_get(bar, 'reason')!r}"
    )

    via = _get(bar, "via")
    assert via is not None
    assert via in ("comp-foo", "G-FOO-001"), f"unexpected via for comp-bar: {via!r}"

    guarantee_ids = _get(bar, "guarantee_ids")
    assert guarantee_ids is not None, "transitive-guarantee entry must carry guarantee_ids"
    guarantee_ids = list(guarantee_ids)
    assert "G-FOO-001" in guarantee_ids, (
        f"comp-bar's entry must name G-FOO-001; got {guarantee_ids!r}"
    )
    # G-FOO-002 never changed, and comp-bar never claimed it.
    assert "G-FOO-002" not in guarantee_ids, (
        f"comp-bar's entry must not name unchanged G-FOO-002; got {guarantee_ids!r}"
    )