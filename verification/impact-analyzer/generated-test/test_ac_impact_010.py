"""AC-IMPACT-010 (covers R-IMPACT-010).

"The prior commit" resolves to the merge-base between HEAD and the repo's
default branch, and per-file change detection compares each relevant file's
content at that commit against its current working-tree content -- never
against HEAD~1, and never inferred from the shape of a --changed id.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import impact_analyzer


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git executable is required"
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "git %s failed (%d):\nstdout:\n%s\nstderr:\n%s"
            % (" ".join(args), proc.returncode, proc.stdout, proc.stderr)
        )
    return proc.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--no-verify", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------
# Locating spec-linter's lint() for the lint-clean precondition check
# ---------------------------------------------------------------------------


def _load_module_from_file(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


def _find_lint():
    try:
        import spec_linter  # noqa: F401

        fn = getattr(spec_linter, "lint", None)
        if callable(fn):
            return fn
    except Exception:
        pass
    here = Path(impact_analyzer.__file__).resolve()
    for ancestor in here.parents:
        base = ancestor / "gen" / "spec-linter"
        flat = base / "spec_linter.py"
        pkg = base / "spec_linter" / "__init__.py"
        for candidate in (flat, pkg):
            if candidate.is_file():
                try:
                    module = _load_module_from_file("spec_linter", candidate)
                except Exception:
                    continue
                fn = getattr(module, "lint", None)
                if callable(fn):
                    return fn
    return None


@pytest.fixture(scope="module")
def lint_fn():
    return _find_lint()


def _assert_lint_clean(lint, repo_root: Path) -> None:
    if lint is None:
        # spec-linter could not be located from this test's environment; the
        # report's own precondition_error (asserted null below) still guards
        # against a non-lint-clean fixture.
        return
    report = lint(None, repo_root)
    findings = _get(report, "findings", []) or []
    fails = [f for f in findings if _get(f, "severity") == "fail"]
    hard = _get(report, "hard_failures", None)
    if hard is None:
        hard = len(fails)
    detail = "\n".join(
        "%s %s:%s %s"
        % (_get(f, "rule_id"), _get(f, "file"), _get(f, "line"), _get(f, "message"))
        for f in fails
    )
    assert hard == 0 and not fails, "fixture is not lint-clean:\n" + detail


# ---------------------------------------------------------------------------
# Synthetic corpus fixture
# ---------------------------------------------------------------------------


LIBRARY_V1 = """# Library

```
foo(x: int) -> int
```

Returns `x` doubled.
"""

LIBRARY_V2 = """# Library

```
foo(x: int) -> int
foo_many(xs: list[int]) -> list[int]
```

`foo` returns `x` doubled; `foo_many` doubles every element of `xs`.
"""


def _component_md(comp_id: str, title: str, purpose: str, depends_on=None) -> str:
    slug = comp_id[len("comp-"):]
    lines = [
        "---",
        "id: %s" % comp_id,
        "title: %s" % title,
        "status: draft",
        "owners: [test-team]",
    ]
    if depends_on:
        lines.append("depends_on: [%s]" % ", ".join(depends_on))
    lines += [
        "sealed: true",
        "source_path: legacy/%s" % slug,
        "---",
        "",
        "# %s" % title,
        "",
        "## Purpose",
        "",
        purpose,
        "",
        "## Rationale",
        "",
        "A minimal fixture component used to exercise impact analysis.",
        "",
        "## Scope",
        "",
        "- In scope: the single function described in its requirements.",
        "- Out of scope: everything else.",
        "",
        "## Definitions",
        "",
        "None beyond the glossary.",
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
        "- Initial fixture version.",
        "",
    ]
    return "\n".join(lines)


def _build_corpus(repo: Path) -> None:
    _write(
        repo,
        "specs/glossary.md",
        "# Glossary\n\n"
        "Canonical vocabulary for this fixture corpus.\n\n"
        "- **Doubling** — multiplying an integer by two.\n",
    )

    # comp-foo
    _write(
        repo,
        "specs/components/foo/component.md",
        _component_md("comp-foo", "Foo", "Doubles integers for its callers."),
    )
    _write(
        repo,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo` MUST return its argument doubled.\n",
    )
    _write(
        repo,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven the integer 2\nWhen foo is called with it\n"
        "Then the result is 4\n```\n",
    )
    _write(repo, "specs/components/foo/interface/library.md", LIBRARY_V1)
    _write(
        repo,
        "specs/components/foo/constraints.md",
        "# Constraints\n\n"
        "- Latency: `foo` MUST return within 10 ms. Measured by a timing test.\n",
    )
    _write(repo, "legacy/foo/foo.txt", "placeholder for sealed source\n")

    # comp-bar, depends_on comp-foo
    _write(
        repo,
        "specs/components/bar/component.md",
        _component_md(
            "comp-bar",
            "Bar",
            "Quadruples integers by calling Foo twice.",
            depends_on=["comp-foo"],
        ),
    )
    _write(
        repo,
        "specs/components/bar/requirements/R-BAR-001.md",
        "# R-BAR-001\n\n**R-BAR-001** — `bar` MUST return its argument "
        "quadrupled, computed by calling `foo` twice.\n",
    )
    _write(
        repo,
        "specs/components/bar/acceptance/AC-BAR-001.md",
        "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: generated-test\n\n"
        "```gherkin\nGiven the integer 2\nWhen bar is called with it\n"
        "Then the result is 8\n```\n",
    )
    _write(
        repo,
        "specs/components/bar/constraints.md",
        "# Constraints\n\n"
        "- Latency: `bar` MUST return within 20 ms. Measured by a timing test.\n",
    )
    _write(repo, "legacy/bar/bar.txt", "placeholder for sealed source\n")

    _write(repo, "notes/scratch.md", "Scratch notes, version 0.\n")


LIB_REL = "specs/components/foo/interface/library.md"


def _init_repo_at_a(tmp_path: Path):
    """Create a repo whose default branch `main` sits at commit A, with an
    `origin` remote whose HEAD also points at main, then fork `feature`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "init.defaultBranch", "main")

    _build_corpus(repo)
    sha_a = _commit(repo, "A: initial corpus")

    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(origin))
    _git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "remote", "set-head", "origin", "main")

    _git(repo, "checkout", "-q", "-b", "feature")
    return repo, sha_a


def _run_impact(repo: Path, monkeypatch):
    monkeypatch.chdir(repo)
    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo)
    assert _get(report, "precondition_error") is None, (
        "unexpected precondition_error: %r" % (_get(report, "precondition_error"),)
    )
    impacted = _get(report, "impacted", []) or []
    return list(impacted)


def _entries_for(impacted, component_id):
    return [e for e in impacted if _get(e, "component_id") == component_id]


def _assert_foo_direct(impacted):
    foo = _entries_for(impacted, "comp-foo")
    assert len(foo) == 1, "comp-foo must appear exactly once: %r" % (impacted,)
    assert _get(foo[0], "reason") == "direct"
    assert _get(foo[0], "via") is None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_interface_change_before_head_parent_detected_via_merge_base(
    tmp_path, monkeypatch, lint_fn
):
    """The exact AC-IMPACT-010 scenario: library.md changed in B, untouched
    in C. HEAD~1 (B) vs working tree shows no change; merge-base (A) vs
    working tree does."""
    repo, sha_a = _init_repo_at_a(tmp_path)

    _write(repo, LIB_REL, LIBRARY_V2)
    sha_b = _commit(repo, "B: change comp-foo's interface")

    _write(repo, "notes/scratch.md", "Scratch notes, version 1.\n")
    sha_c = _commit(repo, "C: unrelated change")

    # Sanity-check the git topology the criterion describes.
    assert _git(repo, "rev-parse", "HEAD") == sha_c
    assert _git(repo, "rev-parse", "HEAD~1") == sha_b
    assert _git(repo, "merge-base", "HEAD", "main") == sha_a
    assert _git(repo, "show", "%s:%s" % (sha_a, LIB_REL)) != _git(
        repo, "show", "%s:%s" % (sha_c, LIB_REL)
    )
    assert _git(repo, "show", "%s:%s" % (sha_b, LIB_REL)) == _git(
        repo, "show", "%s:%s" % (sha_c, LIB_REL)
    )
    assert _git(repo, "status", "--porcelain") == ""

    _assert_lint_clean(lint_fn, repo)

    impacted = _run_impact(repo, monkeypatch)

    _assert_foo_direct(impacted)
    bar = _entries_for(impacted, "comp-bar")
    assert len(bar) == 1, (
        "comp-bar must be impacted exactly once (its upstream's interface "
        "changed since the merge-base): %r" % (impacted,)
    )
    assert _get(bar[0], "reason") == "transitive-interface"
    assert _get(bar[0], "via") == "comp-foo"


def test_change_reverted_since_merge_base_is_not_an_interface_change(
    tmp_path, monkeypatch, lint_fn
):
    """library.md changed in B and reverted in C: identical at the merge-base
    and in the working tree, but different at HEAD~1. Comparing against the
    merge-base finds no interface change, so comp-bar is not impacted as
    transitive-interface."""
    repo, sha_a = _init_repo_at_a(tmp_path)

    _write(repo, LIB_REL, LIBRARY_V2)
    sha_b = _commit(repo, "B: change comp-foo's interface")

    _write(repo, LIB_REL, LIBRARY_V1)
    _commit(repo, "C: revert the interface change")

    assert _git(repo, "rev-parse", "HEAD~1") == sha_b
    assert _git(repo, "merge-base", "HEAD", "main") == sha_a
    assert (repo / LIB_REL).read_text(encoding="utf-8") == LIBRARY_V1
    assert _git(repo, "show", "%s:%s" % (sha_b, LIB_REL)) != LIBRARY_V1.strip()

    _assert_lint_clean(lint_fn, repo)

    impacted = _run_impact(repo, monkeypatch)

    _assert_foo_direct(impacted)
    bar_interface = [
        e
        for e in _entries_for(impacted, "comp-bar")
        if _get(e, "reason") == "transitive-interface"
    ]
    assert not bar_interface, (
        "library.md is identical at the merge-base and in the working tree; "
        "comp-bar must not be reported as transitive-interface: %r" % (impacted,)
    )


def test_uncommitted_working_tree_interface_change_is_detected(
    tmp_path, monkeypatch, lint_fn
):
    """The comparison is against the current working-tree content, not just
    committed history: an uncommitted edit to library.md counts."""
    repo, sha_a = _init_repo_at_a(tmp_path)

    _write(repo, "notes/scratch.md", "Scratch notes, version 1.\n")
    _commit(repo, "B: unrelated change")
    _write(repo, "notes/scratch.md", "Scratch notes, version 2.\n")
    _commit(repo, "C: another unrelated change")

    # Interface change exists only in the working tree.
    _write(repo, LIB_REL, LIBRARY_V2)

    assert _git(repo, "merge-base", "HEAD", "main") == sha_a
    assert _git(repo, "diff", "--quiet", sha_a, "HEAD", "--", LIB_REL) == ""
    assert _git(repo, "status", "--porcelain") != ""

    _assert_lint_clean(lint_fn, repo)

    impacted = _run_impact(repo, monkeypatch)

    _assert_foo_direct(impacted)
    bar = _entries_for(impacted, "comp-bar")
    assert len(bar) == 1, (
        "an uncommitted interface change must still impact comp-bar: %r"
        % (impacted,)
    )
    assert _get(bar[0], "reason") == "transitive-interface"
    assert _get(bar[0], "via") == "comp-foo"