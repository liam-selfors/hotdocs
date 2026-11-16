import importlib.util
import subprocess
import sys
from pathlib import Path

import impact_analyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root: Path, *args: str) -> None:
    cmd = [
        "git",
        "-c", "user.name=hotdocs-test",
        "-c", "user.email=hotdocs-test@example.invalid",
        "-c", "commit.gpgsign=false",
        "-c", "init.defaultBranch=main",
        *args,
    ]
    subprocess.run(
        cmd,
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _commit_all(repo_root: Path, message: str) -> None:
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)


def _component_md(comp_id: str, title: str, slug: str, depends_on=None) -> str:
    lines = [
        "---",
        f"id: {comp_id}",
        f"title: {title}",
        "status: draft",
        "owners: [alice]",
    ]
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines += [
        "sealed: true",
        f"source_path: legacy/{slug}",
        "---",
        "",
        f"# {title}",
        "",
        "## Purpose",
        "",
        f"A small test fixture component named {slug} used to exercise blast-radius computation.",
        "",
        "## Scope",
        "",
        "- In scope: returning its input unchanged.",
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
        "- Initial draft.",
        "",
    ]
    return "\n".join(lines)


def _requirement(req_id: str, sentence: str) -> str:
    return f"# {req_id}\n\n**{req_id}** — {sentence}\n"


def _acceptance(ac_id: str, req_id: str) -> str:
    return (
        f"# {ac_id}\n"
        "\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an integer input\n"
        "When the component is called with it\n"
        "Then the same integer is returned\n"
        "```\n"
    )


def _library(func_name: str, note: str) -> str:
    return (
        "# Library\n"
        "\n"
        "```\n"
        f"{func_name}(x: int) -> int\n"
        "```\n"
        "\n"
        f"The function MUST return its input unchanged. {note}\n"
    )


CONSTRAINTS = "# Constraints\n\n- Latency: each call MUST complete within 1 second, measured by a wall-clock timer.\n"
GLOSSARY = "# Glossary\n\n- **Widget** — a thing used only by this test fixture.\n"


def _build_corpus(repo_root: Path, foo_library_text: str, foo_req_sentence: str) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)

    # comp-foo
    foo = repo_root / "specs" / "components" / "foo"
    _write(foo / "component.md", _component_md("comp-foo", "Foo", "foo"))
    _write(foo / "requirements" / "R-FOO-001.md", _requirement("R-FOO-001", foo_req_sentence))
    _write(foo / "acceptance" / "AC-FOO-001.md", _acceptance("AC-FOO-001", "R-FOO-001"))
    _write(foo / "interface" / "library.md", foo_library_text)
    _write(foo / "constraints.md", CONSTRAINTS)
    _write(repo_root / "legacy" / "foo" / "foo.py", "# placeholder legacy source\n")

    # comp-bar depends_on comp-foo
    bar = repo_root / "specs" / "components" / "bar"
    _write(bar / "component.md", _component_md("comp-bar", "Bar", "bar", depends_on=["comp-foo"]))
    _write(bar / "requirements" / "R-BAR-001.md",
           _requirement("R-BAR-001", "The bar component MUST return its input unchanged."))
    _write(bar / "acceptance" / "AC-BAR-001.md", _acceptance("AC-BAR-001", "R-BAR-001"))
    _write(bar / "constraints.md", CONSTRAINTS)
    _write(repo_root / "legacy" / "bar" / "bar.py", "# placeholder legacy source\n")

    # comp-baz — unrelated, depends on nothing
    baz = repo_root / "specs" / "components" / "baz"
    _write(baz / "component.md", _component_md("comp-baz", "Baz", "baz"))
    _write(baz / "requirements" / "R-BAZ-001.md",
           _requirement("R-BAZ-001", "The baz component MUST return its input unchanged."))
    _write(baz / "acceptance" / "AC-BAZ-001.md", _acceptance("AC-BAZ-001", "R-BAZ-001"))
    _write(baz / "constraints.md", CONSTRAINTS)
    _write(repo_root / "legacy" / "baz" / "baz.py", "# placeholder legacy source\n")


def _tool_root():
    here = Path(impact_analyzer.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_spec_linter():
    root = _tool_root()
    if root is None:
        return None
    base = root / "gen" / "spec-linter"
    flat = base / "spec_linter.py"
    pkg = base / "spec_linter" / "__init__.py"
    module_name = "spec_linter"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    elif pkg.is_file():
        spec = importlib.util.spec_from_file_location(
            module_name, pkg, submodule_search_locations=[str(pkg.parent)]
        )
    else:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    if spec_linter is None or not hasattr(spec_linter, "lint"):
        # Fall back to the target's own precondition check
        # (precondition_error must be null), asserted by the caller.
        return
    report = spec_linter.lint(None, repo_root)
    hard = _get(report, "hard_failures")
    findings = _get(report, "findings") or []
    if hard is None:
        summary = _get(report, "summary") or {}
        hard = _get(summary, "hard_failures", 0)
    failing = [
        (_get(f, "rule_id"), _get(f, "file"), _get(f, "line"), _get(f, "message"))
        for f in findings
        if _get(f, "severity") == "fail"
    ]
    assert hard == 0 and not failing, f"fixture corpus is not lint-clean: {failing}"


def _make_repo(tmp_path: Path, library_versions, req_versions) -> Path:
    """Commit state 0, commit state 1, then leave state 2 uncommitted in
    the working tree, so the change is visible whether "prior commit" is
    read as HEAD~1..HEAD or HEAD..working tree."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _build_corpus(repo_root, library_versions[0], req_versions[0])
    _commit_all(repo_root, "initial")
    _build_corpus(repo_root, library_versions[1], req_versions[1])
    _commit_all(repo_root, "change")
    _build_corpus(repo_root, library_versions[2], req_versions[2])
    return repo_root


def _entries_for(impacted, component_id):
    return [e for e in impacted if _get(e, "component_id") == component_id]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_library_md_change_propagates_transitive_interface_to_dependent(tmp_path):
    req = "The foo component MUST return its input unchanged."
    libs = [
        _library("foo_func", "Version one."),
        _library("foo_func", "Version two, with a changed note."),
        _library("foo_func", "Version three, changed once more."),
    ]
    repo_root = _make_repo(tmp_path, libs, [req, req, req])

    _assert_lint_clean(repo_root)

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo_root)

    precondition_error = _get(report, "precondition_error")
    assert precondition_error is None, f"unexpected precondition error: {precondition_error!r}"

    impacted = list(_get(report, "impacted") or [])

    bar_entries = _entries_for(impacted, "comp-bar")
    assert len(bar_entries) == 1, f"comp-bar must appear exactly once, got {impacted!r}"
    bar = bar_entries[0]
    assert _get(bar, "reason") == "transitive-interface", f"wrong reason: {bar!r}"
    assert _get(bar, "via") == "comp-foo", f"wrong via: {bar!r}"

    foo_entries = _entries_for(impacted, "comp-foo")
    assert len(foo_entries) == 1, f"comp-foo must appear exactly once, got {impacted!r}"
    assert _get(foo_entries[0], "reason") == "direct"
    assert _get(foo_entries[0], "via") is None

    # No bare-slug ids, and an unrelated component is not swept in.
    ids = [_get(e, "component_id") for e in impacted]
    assert "bar" not in ids and "foo" not in ids, f"bare slugs leaked: {ids!r}"
    assert "comp-baz" not in ids, f"unrelated comp-baz should not be impacted: {ids!r}"


def test_non_interface_change_does_not_tag_dependent_transitive_interface(tmp_path):
    lib = _library("foo_func", "Stable note.")
    reqs = [
        "The foo component MUST return its input unchanged.",
        "The foo component MUST return its input unchanged, without copying it.",
        "The foo component MUST return its input unchanged, without copying or logging it.",
    ]
    repo_root = _make_repo(tmp_path, [lib, lib, lib], reqs)

    _assert_lint_clean(repo_root)

    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo_root)

    precondition_error = _get(report, "precondition_error")
    assert precondition_error is None, f"unexpected precondition error: {precondition_error!r}"

    impacted = list(_get(report, "impacted") or [])
    for entry in _entries_for(impacted, "comp-bar"):
        assert _get(entry, "reason") != "transitive-interface", (
            f"comp-bar tagged transitive-interface though no interface file changed: {entry!r}"
        )