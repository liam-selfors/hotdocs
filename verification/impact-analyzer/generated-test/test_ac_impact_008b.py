"""AC-IMPACT-008b (covers R-IMPACT-008).

Given comp-foo has two guarantees, G-FOO-001 and G-FOO-002; comp-bar
depends_on comp-foo and declares depends_on_guarantees: [G-FOO-001] only;
and this commit changes G-FOO-002 but not G-FOO-001,
When `hotdocs impact --changed comp-foo` runs,
Then the report's impacted list does NOT contain comp-bar.

Controls (to rule out a vacuous pass where no guarantee change is detected
at all): comp-baz declares depends_on_guarantees: [G-FOO-002] and comp-qux
declares no depends_on_guarantees; both MUST be included as
transitive-guarantee per R-IMPACT-008.
"""

import importlib.util
import os
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


def _git_env():
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "hotdocs-test",
            "GIT_AUTHOR_EMAIL": "hotdocs-test@example.invalid",
            "GIT_COMMITTER_NAME": "hotdocs-test",
            "GIT_COMMITTER_EMAIL": "hotdocs-test@example.invalid",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=str(root),
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"git {' '.join(args)} failed: {proc.returncode}\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    return proc.stdout


# ---------------------------------------------------------------------------
# Locating spec-linter's lint() for the precondition check
# ---------------------------------------------------------------------------


def _load_module_from(module_name: str, module_path: Path):
    if module_path.name == "__init__.py":
        spec = importlib.util.spec_from_file_location(
            module_name,
            module_path,
            submodule_search_locations=[str(module_path.parent)],
        )
    else:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


def _find_lint():
    try:
        import spec_linter  # noqa: F401

        if hasattr(spec_linter, "lint"):
            return spec_linter.lint
    except Exception:
        pass

    starts = []
    try:
        starts.append(Path(impact_analyzer.__file__).resolve())
    except Exception:
        pass
    starts.append(Path.cwd().resolve() / "_")

    seen = set()
    for start in starts:
        for parent in start.parents:
            if parent in seen:
                continue
            seen.add(parent)
            base = parent / "gen" / "spec-linter"
            for candidate in (
                base / "spec_linter.py",
                base / "spec_linter" / "__init__.py",
            ):
                if candidate.is_file():
                    module = _load_module_from("spec_linter", candidate)
                    if hasattr(module, "lint"):
                        return module.lint
    return None


def _hard_failure_findings(report):
    findings = _get(report, "findings", None) or []
    return [f for f in findings if _get(f, "severity") == "fail"]


def _hard_failure_count(report):
    count = _get(report, "hard_failures", None)
    if count is None:
        summary = _get(report, "summary", None)
        if summary is not None:
            count = _get(summary, "hard_failures", None)
    if count is None:
        count = len(_hard_failure_findings(report))
    return count


# ---------------------------------------------------------------------------
# Synthetic, lint-clean corpus
# ---------------------------------------------------------------------------


G_FOO_001_TEXT = (
    "# G-FOO-001\n"
    "\n"
    "The foo component MUST return its records in ascending order of their "
    "identifier.\n"
)


def _g_foo_002_text(times: str) -> str:
    return (
        "# G-FOO-002\n"
        "\n"
        f"The foo component MUST retry a failed read at most {times} times "
        "before reporting an error.\n"
    )


def _component_md(slug, title, depends_on=None, depends_on_guarantees=None):
    fm = [
        "---",
        f"id: comp-{slug}",
        f"title: {title}",
        "status: draft",
        "owners: [test-team]",
    ]
    if depends_on:
        fm.append(f"depends_on: [{', '.join(depends_on)}]")
    if depends_on_guarantees:
        fm.append(f"depends_on_guarantees: [{', '.join(depends_on_guarantees)}]")
    fm += ["sealed: true", f"source_path: legacy/{slug}", "---"]
    body = [
        "",
        f"# {title}",
        "",
        "## Purpose",
        "",
        f"The {slug} component stores and serves simple records for a test "
        "fixture.",
        "",
        "## Rationale",
        "",
        "This component exists only to exercise dependency analysis in a test.",
        "",
        "## Scope",
        "",
        "- In scope: serving records.",
        "- Out of scope: everything else.",
        "",
        "## Definitions",
        "",
        "No deltas from the glossary.",
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
        "- Initial version.",
        "",
    ]
    return "\n".join(fm + body)


def _write_component(root: Path, slug, upper, title, depends_on=None, dog=None,
                     guarantees=None):
    cdir = root / "specs" / "components" / slug
    _write(cdir / "component.md", _component_md(slug, title, depends_on, dog))
    _write(
        cdir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\nThe {slug} component MUST return every stored "
        "record unchanged when asked for it.\n",
    )
    _write(
        cdir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a stored record\n"
        "When the record is requested\n"
        "Then the returned record equals the stored record\n"
        "```\n",
    )
    _write(
        cdir / "interface" / "data" / f"{title}Record.md",
        f"# `{title}Record`\n\nA record that MUST carry an `id` string field.\n",
    )
    _write(
        cdir / "constraints.md",
        "# Constraints\n\n- A single read MUST complete within 1 second, "
        "measured by timing one read in a test.\n",
    )
    for gid, text in (guarantees or {}).items():
        _write(cdir / "interface" / "guarantees" / f"{gid}.md", text)
    _write(root / "legacy" / slug / "README.txt", f"Hand-maintained {slug}.\n")


def _build_corpus(root: Path, g_foo_002_times: str) -> None:
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture record** — a record served by a fixture "
        "component.\n",
    )
    _write_component(
        root, "foo", "FOO", "Foo",
        guarantees={
            "G-FOO-001": G_FOO_001_TEXT,
            "G-FOO-002": _g_foo_002_text(g_foo_002_times),
        },
    )
    _write_component(root, "bar", "BAR", "Bar",
                     depends_on=["comp-foo"], dog=["G-FOO-001"])
    _write_component(root, "baz", "BAZ", "Baz",
                     depends_on=["comp-foo"], dog=["G-FOO-002"])
    _write_component(root, "qux", "QUX", "Qux", depends_on=["comp-foo"])


G001_REL = "specs/components/foo/interface/guarantees/G-FOO-001.md"
G002_REL = "specs/components/foo/interface/guarantees/G-FOO-002.md"


@pytest.fixture(scope="module")
def scenario(tmp_path_factory):
    root = tmp_path_factory.mktemp("impact_008b_repo")
    _git(root, "init", "-q")

    # Prior commit.
    _build_corpus(root, "three")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "prior state")

    # This commit: G-FOO-002 changes, G-FOO-001 does not.
    _write(root / G002_REL, _g_foo_002_text("five"))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "change G-FOO-002 only")

    # Also leave G-FOO-002 (only) differing in the working tree, so the
    # scenario holds whether "this commit" is read as HEAD vs HEAD~1 or as
    # the working tree vs HEAD.
    _write(root / G002_REL, _g_foo_002_text("seven"))

    committed = set(
        _git(root, "diff", "--name-only", "HEAD~1", "HEAD").split()
    )
    working = set(_git(root, "diff", "--name-only", "HEAD").split())
    assert committed == {G002_REL}, committed
    assert working == {G002_REL}, working

    # Precondition: the fixture corpus lints clean.
    lint = _find_lint()
    if lint is not None:
        lint_report = lint(None, root)
        hard = _hard_failure_count(lint_report)
        assert hard == 0, (
            "synthetic fixture corpus did not lint clean: "
            + repr(
                [
                    (
                        _get(f, "rule_id"),
                        _get(f, "file"),
                        _get(f, "line"),
                        _get(f, "message"),
                    )
                    for f in _hard_failure_findings(lint_report)
                ]
            )
        )

    report = impact_analyzer.compute_blast_radius(["comp-foo"], root)
    return {"root": root, "report": report}


def _impacted_by_id(report):
    assert _get(report, "precondition_error", None) is None, (
        f"unexpected precondition_error: {_get(report, 'precondition_error')!r}"
    )
    impacted = _get(report, "impacted", None)
    assert impacted is not None, "report has no 'impacted' list"
    impacted = list(impacted)
    ids = [_get(e, "component_id") for e in impacted]
    assert len(ids) == len(set(ids)), f"component listed more than once: {ids}"
    return {cid: e for cid, e in zip(ids, impacted)}


def _guarantee_ids(entry):
    gids = _get(entry, "guarantee_ids", None)
    return list(gids) if gids is not None else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_bar_not_impacted_when_only_undeclared_guarantee_changed(scenario):
    by_id = _impacted_by_id(scenario["report"])
    assert "comp-bar" not in by_id, (
        "comp-bar declared depends_on_guarantees: [G-FOO-001] only, and only "
        f"G-FOO-002 changed, yet it was reported impacted: {by_id.get('comp-bar')!r}"
    )
    assert "bar" not in by_id


def test_changed_component_itself_is_direct(scenario):
    by_id = _impacted_by_id(scenario["report"])
    assert "comp-foo" in by_id, f"comp-foo missing from impacted: {list(by_id)}"
    entry = by_id["comp-foo"]
    assert _get(entry, "reason") == "direct"
    assert _get(entry, "via") is None


def test_dependent_declaring_changed_guarantee_is_impacted(scenario):
    by_id = _impacted_by_id(scenario["report"])
    assert "comp-baz" in by_id, (
        "control: comp-baz declared depends_on_guarantees: [G-FOO-002], which "
        f"changed, but it was not reported impacted: {list(by_id)}"
    )
    entry = by_id["comp-baz"]
    assert _get(entry, "reason") == "transitive-guarantee"
    assert _get(entry, "via") == "comp-foo"
    gids = _guarantee_ids(entry)
    assert gids is not None, "transitive-guarantee entry lacks guarantee_ids"
    assert "G-FOO-002" in gids
    assert "G-FOO-001" not in gids


def test_dependent_without_declaration_gets_coarse_default(scenario):
    by_id = _impacted_by_id(scenario["report"])
    assert "comp-qux" in by_id, (
        "control: comp-qux declared no depends_on_guarantees, so any change "
        f"under comp-foo's guarantees MUST include it: {list(by_id)}"
    )
    entry = by_id["comp-qux"]
    assert _get(entry, "reason") == "transitive-guarantee"
    assert _get(entry, "via") == "comp-foo"
    gids = _guarantee_ids(entry)
    assert gids is not None, "transitive-guarantee entry lacks guarantee_ids"
    assert sorted(gids) == ["G-FOO-002"]