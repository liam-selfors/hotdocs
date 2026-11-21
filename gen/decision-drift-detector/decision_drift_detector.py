"""Decision Drift Detector.

Flags live spec-file ``D<N>`` citations whose cited decision has since been
superseded by a decision ratified after the citing file's own last-touching
commit (``find_decision_drift``), and reports everything that would be
affected by altering a decision (``find_decision_impact``). Purely
diagnostic: reads only, never gates anything.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import duckdb

CITATION_RE = re.compile(r"\bD\d+\b")

_DEPENDENCY_SLUG = "graph-query-engine"
_DEPENDENCY_MODULE = "graph_query_engine"

_MODULE_CACHE: dict = {}

_USAGE_DRIFT = "usage: hotdocs decision-drift [--format=json|text] [--repo-root=<dir>]"
_USAGE_IMPACT = (
    "usage: hotdocs decision-impact <decision-id> [--format=json|text] [--repo-root=<dir>]"
)


class UsageError(Exception):
    """A usage error: reported as exit code 2 by ``main``."""


# ---------------------------------------------------------------------------
# Dependency resolution (R-DRIFT-004)
# ---------------------------------------------------------------------------


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_dependency(repo_root, slug: str, module_name: str):
    key = (str(repo_root), module_name)
    if key in _MODULE_CACHE:
        return _MODULE_CACHE[key]
    dep_dir = Path(repo_root) / "gen" / slug
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / slug
    flat = dep_dir / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg_dir = dep_dir / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[key] = module
    return module


def _open_graph(repo_root):
    gqe = _load_dependency(repo_root, _DEPENDENCY_SLUG, _DEPENDENCY_MODULE)
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    gqe.load_views(con, Path(repo_root))
    return con


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decision_key(decision_id: str):
    return (int(decision_id[1:]), decision_id)


def _git(repo_root, *args):
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )


def _require_git_repo(repo_root) -> None:
    result = _git(repo_root, "rev-parse", "--git-dir")
    if result.returncode != 0:
        raise UsageError(f"not a git repository: {repo_root}")


def _is_ancestor(repo_root, older: str, newer: str) -> bool:
    return _git(repo_root, "merge-base", "--is-ancestor", older, newer).returncode == 0


def _live_files(repo_root):
    """Yield (relative posix path, citations set) for every live spec file."""
    root = Path(repo_root)
    specs = root / "specs"
    for path in sorted(specs.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("specs/decisions/"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        yield rel, set(CITATION_RE.findall(text))


def _edges(con, edge_types):
    placeholders = ", ".join("?" for _ in edge_types)
    rows = con.execute(
        f"SELECT source_id, target_id FROM edges WHERE edge_type IN ({placeholders})",
        list(edge_types),
    ).fetchall()
    by_target: dict = {}
    for source_id, target_id in rows:
        by_target.setdefault(target_id, set()).add(source_id)
    return by_target


def _closure(by_target: dict, start: str) -> set:
    seen: set = set()
    stack = [start]
    while stack:
        current = stack.pop()
        for source in by_target.get(current, ()):
            if source not in seen and source != start:
                seen.add(source)
                stack.append(source)
    return seen


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def find_decision_drift(repo_root: Path) -> dict:
    _require_git_repo(repo_root)
    con = _open_graph(repo_root)
    try:
        superseded_by = _edges(con, ["supersedes"])
        lineage = {
            row[0]: row[1]
            for row in con.execute(
                "SELECT id, last_ratified_commit FROM decision_lineage"
            ).fetchall()
        }
    finally:
        con.close()

    latest_cache: dict = {}

    def latest_superseder(decision_id: str):
        if decision_id in latest_cache:
            return latest_cache[decision_id]
        best = None
        for cand in sorted(_closure(superseded_by, decision_id), key=_decision_key):
            commit = lineage.get(cand)
            if not commit:
                continue
            if best is None or (
                best[1] != commit and _is_ancestor(repo_root, best[1], commit)
            ):
                best = (cand, commit)
        latest_cache[decision_id] = best
        return best

    entries = []
    for rel, citations in _live_files(repo_root):
        file_commit = None
        for cited in sorted(citations, key=_decision_key):
            found = latest_superseder(cited)
            if found is None:
                continue
            if file_commit is None:
                file_commit = _git(
                    repo_root, "log", "-1", "--format=%H", "--", rel
                ).stdout.strip()
                if not file_commit:
                    raise UsageError(f"no commit history for {rel}")
            superseder, superseder_commit = found
            if _is_ancestor(repo_root, file_commit, superseder_commit):
                entries.append(
                    {
                        "file": rel,
                        "cited_decision": cited,
                        "superseded_by": superseder,
                        "file_commit": file_commit,
                        "superseder_ratified_commit": superseder_commit,
                    }
                )
    return {"entries": entries}


def find_decision_impact(repo_root: Path, decision_id: str) -> dict:
    con = _open_graph(repo_root)
    try:
        dependents = _edges(con, ["supersedes", "builds_on"])
    finally:
        con.close()
    dependent_decisions = sorted(_closure(dependents, decision_id), key=_decision_key)
    citing_files = [
        rel for rel, citations in _live_files(repo_root) if decision_id in citations
    ]
    return {
        "decision_id": decision_id,
        "dependent_decisions": dependent_decisions,
        "citing_files": citing_files,
    }


# ---------------------------------------------------------------------------
# CLI (R-DRIFT-005)
# ---------------------------------------------------------------------------


def _render_drift(report: dict) -> str:
    entries = report["entries"]
    if not entries:
        return "No decision drift found."
    lines = [f"{len(entries)} decision drift candidate(s):"]
    for e in entries:
        lines.append(
            f"  {e['file']}: cites {e['cited_decision']}, superseded by "
            f"{e['superseded_by']} (file commit {e['file_commit']} predates "
            f"ratification {e['superseder_ratified_commit']})"
        )
    return "\n".join(lines)


def _render_impact(report: dict) -> str:
    lines = [f"Impact of altering {report['decision_id']}:"]
    deps = report["dependent_decisions"]
    lines.append("Dependent decisions: " + (", ".join(deps) if deps else "(none)"))
    files = report["citing_files"]
    lines.append("Citing files:" + ("" if files else " (none)"))
    for f in files:
        lines.append(f"  {f}")
    return "\n".join(lines)


def _usage_error(cause: str, usage: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)
    both_usage = _USAGE_DRIFT + "\n" + _USAGE_IMPACT

    if not args or args[0] not in ("decision-drift", "decision-impact"):
        return _usage_error("missing or unknown subcommand", both_usage)
    command = args.pop(0)
    usage = _USAGE_DRIFT if command == "decision-drift" else _USAGE_IMPACT

    fmt = "text"
    repo_root_arg = None
    positionals = []
    i = 0
    while i < len(args):
        token = args[i]
        name, eq, value = token.partition("=")
        if name in ("--format", "--repo-root"):
            if not eq:
                if i + 1 >= len(args):
                    return _usage_error(f"{name} requires a value", usage)
                i += 1
                value = args[i]
            if name == "--format":
                if value not in ("json", "text"):
                    return _usage_error(f"invalid --format value: {value}", usage)
                fmt = value
            else:
                repo_root_arg = value
        elif token.startswith("-"):
            return _usage_error(f"unknown argument: {token}", usage)
        else:
            positionals.append(token)
        i += 1

    if command == "decision-impact":
        if not positionals:
            return _usage_error("missing <decision-id>", usage)
        if len(positionals) > 1:
            return _usage_error(f"unknown argument: {positionals[1]}", usage)
    elif positionals:
        return _usage_error(f"unknown argument: {positionals[0]}", usage)

    if repo_root_arg is None:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
        )
        if top.returncode != 0:
            return _usage_error("not a git repository", usage)
        repo_root = Path(top.stdout.strip())
    else:
        repo_root = Path(repo_root_arg)
        if not repo_root.is_dir():
            return _usage_error(f"unreadable --repo-root: {repo_root_arg}", usage)

    try:
        _require_git_repo(repo_root)
        if command == "decision-drift":
            report = find_decision_drift(repo_root)
            text = _render_drift(report)
        else:
            report = find_decision_impact(repo_root, positionals[0])
            text = _render_impact(report)
    except UsageError as exc:
        return _usage_error(str(exc), usage)

    if fmt == "json":
        print(json.dumps(report, indent=2))
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
