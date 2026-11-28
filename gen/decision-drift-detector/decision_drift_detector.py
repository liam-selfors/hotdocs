"""Decision Drift Detector.

Flags live spec files whose cited ``D<N>`` decision has since been
superseded by a decision ratified after the citing file's own last
commit (``find_decision_drift``), and reports what would be affected by
altering a decision (``find_decision_impact``). Purely diagnostic.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import duckdb

__all__ = ["find_decision_drift", "find_decision_impact", "main", "UsageError"]

_CITATION_RE = re.compile(r"\bD\d+\b")

_USAGE_DRIFT = "usage: hotdocs decision-drift [--format=json|text] [--repo-root=<dir>]"
_USAGE_IMPACT = (
    "usage: hotdocs decision-impact <decision-id> [--format=json|text] [--repo-root=<dir>]"
)
_USAGES = {"decision-drift": _USAGE_DRIFT, "decision-impact": _USAGE_IMPACT}
_USAGE_ALL = _USAGE_DRIFT + "\n" + _USAGE_IMPACT

_MODULE_CACHE: dict = {}


class UsageError(Exception):
    """A usage error: bad arguments, not a git repository, or missing history."""


class _Report(dict):
    """A dict whose keys are also readable as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


# --------------------------------------------------------------------------
# Dependency loading (R-DRIFT-004)
# --------------------------------------------------------------------------


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_dependency(repo_root: Path, slug: str, module_name: str):
    key = (str(repo_root), module_name)
    if key in _MODULE_CACHE:
        return _MODULE_CACHE[key]
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    load_name = f"_decision_drift_detector_dep_{module_name}_{len(_MODULE_CACHE)}"
    package_init = base / module_name / "__init__.py"
    if package_init.is_file():
        spec = importlib.util.spec_from_file_location(
            load_name, package_init, submodule_search_locations=[str(package_init.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location(load_name, base / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[key] = module
    return module


def _dep_get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name)


def _open_views(repo_root: Path):
    gqe = _load_dependency(repo_root, "graph-query-engine", "graph_query_engine")
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    _dep_get(gqe, "load_views")(con, Path(repo_root))
    return con


# --------------------------------------------------------------------------
# Git helpers
# --------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo_root), capture_output=True, text=True
    )


def _require_git(repo_root: Path) -> None:
    if _git(repo_root, "rev-parse", "--git-dir").returncode != 0:
        raise UsageError(f"not a git repository: {repo_root}")


def _file_commit(repo_root: Path, rel_path: str) -> str:
    commit = _git(repo_root, "log", "-1", "--format=%H", "--", rel_path).stdout.strip()
    if not commit:
        raise UsageError(f"no commit history for cited file: {rel_path}")
    return commit


def _is_ancestor(repo_root: Path, older: str, newer: str) -> bool:
    return _git(repo_root, "merge-base", "--is-ancestor", older, newer).returncode == 0


# --------------------------------------------------------------------------
# Corpus helpers
# --------------------------------------------------------------------------


def _decision_key(decision_id: str):
    return (len(decision_id), decision_id)


def _live_citations(repo_root: Path):
    """Yield (relative_path, sorted citations) for every live spec file."""
    result = []
    for path in sorted((Path(repo_root) / "specs").rglob("*.md")):
        rel = path.relative_to(repo_root).as_posix()
        if rel.startswith("specs/decisions/"):
            continue
        cited = set(_CITATION_RE.findall(path.read_text(encoding="utf-8")))
        result.append((rel, sorted(cited, key=_decision_key)))
    return result


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------


def find_decision_drift(repo_root: Path) -> _Report:
    repo_root = Path(repo_root)
    _require_git(repo_root)
    con = _open_views(repo_root)
    superseders: dict = {}
    for source_id, target_id in con.execute(
        "SELECT source_id, target_id FROM edges WHERE edge_type = 'supersedes'"
    ).fetchall():
        superseders.setdefault(target_id, set()).add(source_id)
    ratified = dict(
        con.execute("SELECT id, last_ratified_commit FROM decision_lineage").fetchall()
    )
    con.close()

    latest_cache: dict = {}

    def latest_superseder(decision_id: str):
        if decision_id in latest_cache:
            return latest_cache[decision_id]
        seen: set = set()
        frontier = [decision_id]
        while frontier:
            current = frontier.pop()
            for newer in superseders.get(current, ()):
                if newer not in seen:
                    seen.add(newer)
                    frontier.append(newer)
        seen.discard(decision_id)
        latest = None
        for candidate in sorted(seen, key=_decision_key):
            commit = ratified.get(candidate)
            if commit is None:
                continue
            if latest is None or _is_ancestor(repo_root, latest[1], commit):
                latest = (candidate, commit)
        latest_cache[decision_id] = latest
        return latest

    entries = []
    for rel, cited in _live_citations(repo_root):
        file_commit = None
        for decision_id in cited:
            latest = latest_superseder(decision_id)
            if latest is None:
                continue
            if file_commit is None:
                file_commit = _file_commit(repo_root, rel)
            superseder_id, superseder_commit = latest
            if _is_ancestor(repo_root, file_commit, superseder_commit):
                entries.append(
                    _Report(
                        file=rel,
                        cited_decision=decision_id,
                        superseded_by=superseder_id,
                        file_commit=file_commit,
                        superseder_ratified_commit=superseder_commit,
                    )
                )
    return _Report(entries=entries)


def find_decision_impact(repo_root: Path, decision_id: str) -> _Report:
    repo_root = Path(repo_root)
    con = _open_views(repo_root)
    dependents_of: dict = {}
    for source_id, target_id in con.execute(
        "SELECT source_id, target_id FROM edges "
        "WHERE edge_type IN ('supersedes', 'builds_on')"
    ).fetchall():
        dependents_of.setdefault(target_id, set()).add(source_id)
    con.close()

    seen: set = set()
    frontier = [decision_id]
    while frontier:
        current = frontier.pop()
        for dependent in dependents_of.get(current, ()):
            if dependent not in seen:
                seen.add(dependent)
                frontier.append(dependent)
    seen.discard(decision_id)

    citing_files = [rel for rel, cited in _live_citations(repo_root) if decision_id in cited]
    return _Report(
        decision_id=decision_id,
        dependent_decisions=sorted(seen, key=_decision_key),
        citing_files=citing_files,
    )


# --------------------------------------------------------------------------
# CLI (R-DRIFT-005)
# --------------------------------------------------------------------------


def _render_drift_text(report) -> str:
    entries = report["entries"]
    if not entries:
        return "No decision drift candidates."
    lines = [f"{len(entries)} decision drift candidate(s):"]
    for e in entries:
        lines.append(
            f"  {e['file']}: cites {e['cited_decision']}, superseded by "
            f"{e['superseded_by']} (file commit {e['file_commit']} predates "
            f"ratification {e['superseder_ratified_commit']})"
        )
    return "\n".join(lines)


def _render_impact_text(report) -> str:
    lines = [f"Decision {report['decision_id']}"]
    lines.append(
        "Dependent decisions: " + (", ".join(report["dependent_decisions"]) or "(none)")
    )
    lines.append("Citing files:" + ("" if report["citing_files"] else " (none)"))
    lines.extend(f"  {path}" for path in report["citing_files"])
    return "\n".join(lines)


def _run(command, tokens) -> int:
    if command not in _USAGES:
        raise UsageError(f"unknown or missing subcommand: {command!r}")
    fmt = "text"
    root_arg = None
    positional = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        name, eq, value = tok.partition("=")
        if name in ("--format", "--repo-root"):
            if not eq:
                i += 1
                if i >= len(tokens):
                    raise UsageError(f"{name} requires a value")
                value = tokens[i]
            if name == "--format":
                fmt = value
            else:
                root_arg = value
        elif tok.startswith("-"):
            raise UsageError(f"unknown argument: {tok}")
        else:
            positional.append(tok)
        i += 1

    if fmt not in ("json", "text"):
        raise UsageError(f"invalid --format value: {fmt}")
    expected = 1 if command == "decision-impact" else 0
    if len(positional) < expected:
        raise UsageError("missing <decision-id>")
    if len(positional) > expected:
        raise UsageError(f"unexpected argument: {positional[expected]}")

    if root_arg is None:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
        )
        if top.returncode != 0:
            raise UsageError("not a git repository")
        repo_root = Path(top.stdout.strip())
    else:
        repo_root = Path(root_arg)
        if not repo_root.is_dir():
            raise UsageError(f"unreadable --repo-root: {root_arg}")
    _require_git(repo_root)

    if command == "decision-drift":
        report = find_decision_drift(repo_root)
        text = _render_drift_text(report)
    else:
        report = find_decision_impact(repo_root, positional[0])
        text = _render_impact_text(report)
    print(json.dumps(report, indent=2) if fmt == "json" else text)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else None
    usage = _USAGES.get(command, _USAGE_ALL)
    try:
        return _run(command, args[1:])
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(usage, file=sys.stderr)
        return 2
