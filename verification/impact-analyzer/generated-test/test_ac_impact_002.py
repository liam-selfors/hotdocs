"""AC-IMPACT-002 (covers R-IMPACT-002).

Given comp-foo's component.md changed but every file under its interface/
  is byte-identical to the prior commit, and comp-bar depends_on comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-foo with reason "direct" and
  does NOT contain comp-bar
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
# helpers
# ---------------------------------------------------------------------------

def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    cmd = [
        "git",
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "init.defaultBranch=main",
        *args,
    ]
    result = subprocess.run(
        cmd, cwd=str(repo_root), env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed: {result.stdout}\n{result.stderr}"
    )
    return result


def _component_md(comp_id, title, purpose, depends_on=None):
    lines = [
        "---",
        f"id: {comp_id}",
        f"title: {title}",
        "status: draft",
        "owners: [test-owner]",
    ]
    if depends_on:
        lines.append(f"depends_on: [{', '.join(depends_on)}]")
    slug = comp_id[len("comp-"):]
    lines.append("sealed: true")
    lines.append(f"source_path: legacy/{slug}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(purpose)
    lines.append("")
    lines.append("## Rationale")
    lines.append("")
    lines.append("A minimal synthetic fixture used only by an acceptance test.")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- In scope: the single function in its library contract.")
    lines.append("- Out of scope: everything else.")
    lines.append("")
    lines.append("## Definitions")
    lines.append("")
    lines.append("None beyond the glossary.")
    lines.append("")
    lines.append("## Behavior")
    lines.append("")
    lines.append("See `requirements/`.")
    lines.append("")
    lines.append("## Interfaces")
    lines.append("")
    lines.append("See `interface/`.")
    lines.append("")
    lines.append("## Data")
    lines.append("")
    lines.append("See `interface/data/`.")
    lines.append("")
    lines.append("## Acceptance criteria")
    lines.append("")
    lines.append("See `acceptance/`.")
    lines.append("")
    lines.append("## Non-functional constraints")
    lines.append("")
    lines.append("See `constraints.md`.")
    lines.append("")
    lines.append("## Open questions")
    lines.append("")
    lines.append("## Change log")
    lines.append("")
    lines.append("- Initial version.")
    lines.append("")
    return "\n".join(lines)


def _build_component(repo_root, comp_id, title, req_prefix, func_name,
                     purpose, depends_on=None):
    slug = comp_id[len("comp-"):]
    cdir = repo_root / "specs" / "components" / slug
    _write(cdir / "component.md",
           _component_md(comp_id, title, purpose, depends_on))
    req_id = f"R-{req_prefix}-001"
    ac_id = f"AC-{req_prefix}-001"
    _write(
        cdir / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\n"
        f"**{req_id}** — `{func_name}(x)` MUST return `x` unchanged.\n",
    )
    _write(
        cdir / "acceptance" / f"{ac_id}.md",
        f"# {ac_id}\n\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given an integer x\n"
        f"When {func_name}(x) is called\n"
        "Then the result equals x\n"
        "```\n",
    )
    _write(
        cdir / "interface" / "library.md",
        "# Library\n\n"
        "```\n"
        f"{func_name}(x: int) -> int\n"
        "```\n\n"
        "Returns its argument unchanged.\n",
    )
    _write(
        cdir / "constraints.md",
        "# Constraints\n\n"
        "- Latency: a call MUST complete in under 1 second, measured by a "
        "timed unit test.\n",
    )
    legacy = repo_root / "legacy" / slug
    legacy.mkdir(parents=True, exist_ok=True)
    _write(legacy / f"{slug.replace('-', '_')}.py",
           f"def {func_name}(x):\n    return x\n")
    return cdir


def _find_lint():
    """Locate spec-linter's lint() via the documented gen/<slug>/ layout,
    searching upward from the component under test's own location."""
    try:
        start = Path(impact_analyzer.__file__).resolve()
    except Exception:
        return None
    for parent in start.parents:
        flat = parent / "gen" / "spec-linter" / "spec_linter.py"
        pkg = parent / "gen" / "spec-linter" / "spec_linter" / "__init__.py"
        module_path = None
        search = None
        if flat.is_file():
            module_path = flat
        elif pkg.is_file():
            module_path = pkg
            search = [str(pkg.parent)]
        if module_path is None:
            continue
        module_name = "spec_linter"
        if search is not None:
            spec = importlib.util.spec_from_file_location(
                module_name, module_path, submodule_search_locations=search
            )
        else:
            spec = importlib.util.spec_from_file_location(
                module_name, module_path
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)
        return getattr(module, "lint", None)
    try:
        import spec_linter  # noqa: F401
        return getattr(spec_linter, "lint", None)
    except Exception:
        return None


def _hard_failures(report):
    hf = _field(report, "hard_failures")
    if hf is None:
        summary = _field(report, "summary")
        if summary is not None:
            hf = _field(summary, "hard_failures")
    if hf is None:
        findings = _field(report, "findings") or []
        hf = sum(1 for f in findings if _field(f, "severity") == "fail")
    return hf


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def repo_root(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to build the prior-commit fixture")

    root = tmp_path / "repo"
    root.mkdir()

    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n"
        "- **Fixture term** — a term used only by this synthetic test "
        "corpus.\n",
    )
    _build_component(
        root, "comp-foo", "Foo", "FOO", "foo",
        "Foo returns its integer input unchanged, for use by dependents.",
    )
    _build_component(
        root, "comp-bar", "Bar", "BAR", "bar",
        "Bar returns its integer input unchanged, delegating to foo.",
        depends_on=["comp-foo"],
    )

    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial corpus")

    # Change only comp-foo's component.md narrative (Purpose), leaving every
    # file under its interface/ byte-identical.
    foo_md = root / "specs" / "components" / "foo" / "component.md"
    text = foo_md.read_text(encoding="utf-8")
    new_text = text.replace(
        "Foo returns its integer input unchanged, for use by dependents.",
        "Foo returns its integer input unchanged, so dependents can rely "
        "on an identity transform.",
    )
    assert new_text != text
    foo_md.write_text(new_text, encoding="utf-8")

    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "narrative-only change to comp-foo")
    return root


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

def test_internal_only_change_does_not_propagate_to_dependents(repo_root):
    foo_dir = repo_root / "specs" / "components" / "foo"

    # Sanity: the prior commit changed component.md and nothing under
    # interface/.
    changed = _git(
        repo_root, "diff", "--name-only", "HEAD~1", "HEAD"
    ).stdout.split()
    assert "specs/components/foo/component.md" in changed
    assert not any(
        p.startswith("specs/components/foo/interface/") for p in changed
    ), changed
    for iface_file in (foo_dir / "interface").rglob("*"):
        if iface_file.is_file():
            rel = iface_file.relative_to(repo_root).as_posix()
            prior = subprocess.run(
                ["git", "show", f"HEAD~1:{rel}"],
                cwd=str(repo_root), capture_output=True,
            )
            assert prior.returncode == 0
            assert prior.stdout == iface_file.read_bytes(), rel
    # Nothing uncommitted either.
    status = _git(repo_root, "status", "--porcelain").stdout.strip()
    assert status == ""

    # Precondition: the corpus lints clean.
    lint = _find_lint()
    if lint is not None:
        lint_report = lint(None, repo_root)
        hf = _hard_failures(lint_report)
        findings = _field(lint_report, "findings") or []
        details = [
            (
                _field(f, "rule_id"),
                _field(f, "file"),
                _field(f, "line"),
                _field(f, "message"),
            )
            for f in findings
            if _field(f, "severity") == "fail"
        ]
        assert hf == 0, f"fixture corpus is not lint-clean: {details}"

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo_root)

    precondition_error = _field(report, "precondition_error")
    assert precondition_error is None, (
        f"unexpected precondition_error: {precondition_error}"
    )

    impacted = _field(report, "impacted")
    assert impacted is not None
    impacted = list(impacted)

    ids = [_field(entry, "component_id") for entry in impacted]

    # Each component appears at most once.
    assert len(ids) == len(set(ids)), ids

    # comp-foo is present, as "direct", with via null.
    foo_entries = [e for e in impacted if _field(e, "component_id") == "comp-foo"]
    assert len(foo_entries) == 1, ids
    assert _field(foo_entries[0], "reason") == "direct"
    assert _field(foo_entries[0], "via") is None

    # comp-bar is NOT in the blast radius on any basis.
    assert "comp-bar" not in ids, impacted
    assert "bar" not in ids, impacted