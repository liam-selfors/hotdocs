"""Decision Drift Detector: comp-decision-drift-detector.

Pure, read-only library + CLI over git history and the spec corpus.
Never gates anything; purely diagnostic.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:  # pragma: no cover - duckdb is a hard runtime dependency
    duckdb = None

_CITATION_RE = re.compile(r"\bD\d+\b")

_MODULE_CACHE: dict[tuple[str, str], object] = {}


class UsageError(Exception):
    """Raised for anything interface/cli.md documents as exit code 2."""


# --------------------------------------------------------------------------
# Dynamic dependency loading (R-DRIFT-004)
# --------------------------------------------------------------------------


def _find_tool_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if candidate.name == "gen":
            return candidate.parent
    raise RuntimeError("could not locate a 'gen' ancestor directory above this module")


def _load_dependency_module(repo_root: Path, dep_dir_name: str, module_name: str):
    repo_root = Path(repo_root)
    cache_key = (str(repo_root), module_name)
    if cache_key in _MODULE_CACHE:
        return _MODULE_CACHE[cache_key]

    candidate_dir = repo_root / "gen" / dep_dir_name
    if not candidate_dir.exists():
        tool_root = _find_tool_root(Path(__file__).resolve())
        candidate_dir = tool_root / "gen" / dep_dir_name

    flat_path = candidate_dir / f"{module_name}.py"
    pkg_path = candidate_dir / module_name / "__init__.py"

    if flat_path.exists():
        module_path = flat_path
    elif pkg_path.exists():
        module_path = pkg_path
    else:
        raise RuntimeError(
            f"dependency module {module_name!r} not found under {candidate_dir}"
        )

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    # Must be registered before exec_module: dataclasses defined in the
    # dependency look themselves up in sys.modules[cls.__module__] while
    # their own class body is executing.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    _MODULE_CACHE[cache_key] = module
    return module


def _build_connection(repo_root: Path):
    gqe = _load_dependency_module(repo_root, "graph-query-engine", "graph_query_engine")
    con = duckdb.connect(":memory:")
    try:
        con.execute("INSTALL yaml FROM community")
    except Exception:
        pass
    con.execute("LOAD yaml")

    load_views = getattr(gqe, "load_views", None)
    if load_views is None:
        load_views = gqe["load_views"]
    load_views(con, repo_root)
    return con


# --------------------------------------------------------------------------
# git helpers
# --------------------------------------------------------------------------


def _run_git(repo_root: Path, args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _check_git_repo(repo_root: Path) -> None:
    repo_root = Path(repo_root)
    if not repo_root.is_dir():
        raise UsageError(f"not a readable directory: {repo_root}")
    try:
        rc, out, _err = _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    except OSError as exc:
        raise UsageError(f"failed to run git in {repo_root}: {exc}") from exc
    if rc != 0 or out != "true":
        raise UsageError(f"{repo_root} is not a git repository")


def _file_last_commit(repo_root: Path, rel_path: str) -> str:
    rc, out, err = _run_git(repo_root, ["log", "-1", "--format=%H", "--", rel_path])
    if rc != 0:
        raise UsageError(f"git log failed for {rel_path}: {err}")
    if not out:
        raise UsageError(f"{rel_path} has no commit history (uncommitted)")
    return out


def _is_ancestor(repo_root: Path, ancestor_commit: str, descendant_commit: str) -> bool:
    rc, _out, _err = _run_git(
        repo_root, ["merge-base", "--is-ancestor", ancestor_commit, descendant_commit]
    )
    return rc == 0


# --------------------------------------------------------------------------
# Live spec corpus
# --------------------------------------------------------------------------


def _live_spec_files(repo_root: Path) -> list[Path]:
    specs_dir = Path(repo_root) / "specs"
    if not specs_dir.is_dir():
        return []
    files = []
    for path in sorted(specs_dir.rglob("*.md")):
        rel = path.relative_to(repo_root)
        parts = rel.parts
        if len(parts) >= 2 and parts[1] == "decisions":
            continue
        files.append(rel)
    return files


def _extract_citations(text: str) -> set[str]:
    return set(_CITATION_RE.findall(text))


# --------------------------------------------------------------------------
# R-DRIFT-001 / R-DRIFT-002: find_decision_drift
# --------------------------------------------------------------------------


def _build_supersede_map(edge_rows) -> dict[str, list[str]]:
    m: dict[str, list[str]] = {}
    for source_id, target_id in edge_rows:
        m.setdefault(target_id, []).append(source_id)
    return m


def _latest_candidate(repo_root: Path, candidates: list[str], lineage: dict) -> str:
    with_commit = [(c, lineage.get(c)) for c in candidates]
    with_commit = [(c, commit) for c, commit in with_commit if commit]
    if not with_commit:
        return candidates[0]
    best, best_commit = with_commit[0]
    for candidate, commit in with_commit[1:]:
        # candidate is "later" than best if best's commit is an ancestor
        # of candidate's commit (ratification order, not D<N> order).
        if _is_ancestor(repo_root, best_commit, commit):
            best, best_commit = candidate, commit
    return best


def _walk_to_latest_superseder(
    repo_root: Path, decision_id: str, supersede_map: dict, lineage: dict
) -> str | None:
    current = decision_id
    latest = None
    visited = {current}
    while True:
        next_candidates = [
            c for c in supersede_map.get(current, []) if c not in visited
        ]
        if not next_candidates:
            break
        chosen = _latest_candidate(repo_root, next_candidates, lineage)
        latest = chosen
        visited.add(chosen)
        current = chosen
    return latest


def find_decision_drift(repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    _check_git_repo(repo_root)

    con = _build_connection(repo_root)
    edge_rows = con.execute(
        "SELECT source_id, target_id FROM edges WHERE edge_type = 'supersedes'"
    ).fetchall()
    supersede_map = _build_supersede_map(edge_rows)

    lineage_rows = con.execute(
        "SELECT id, last_ratified_commit FROM decision_lineage"
    ).fetchall()
    lineage = {row[0]: row[1] for row in lineage_rows}

    entries = []
    for rel_path in _live_spec_files(repo_root):
        text = (repo_root / rel_path).read_text(encoding="utf-8")
        citations = _extract_citations(text)
        for cited in sorted(citations):
            superseder = _walk_to_latest_superseder(repo_root, cited, supersede_map, lineage)
            if superseder is None:
                continue
            superseder_commit = lineage.get(superseder)
            if not superseder_commit:
                continue
            file_commit = _file_last_commit(repo_root, str(rel_path))
            if _is_ancestor(repo_root, file_commit, superseder_commit):
                entries.append(
                    {
                        "file": str(rel_path),
                        "cited_decision": cited,
                        "superseded_by": superseder,
                        "file_commit": file_commit,
                        "superseder_ratified_commit": superseder_commit,
                    }
                )

    return {"entries": entries}


# --------------------------------------------------------------------------
# R-DRIFT-003: find_decision_impact
# --------------------------------------------------------------------------


def find_decision_impact(repo_root: Path, decision_id: str) -> dict:
    repo_root = Path(repo_root)
    _check_git_repo(repo_root)
    if not decision_id:
        raise UsageError("decision_id is required")

    con = _build_connection(repo_root)
    edge_rows = con.execute(
        "SELECT source_id, target_id FROM edges "
        "WHERE edge_type IN ('supersedes', 'builds_on')"
    ).fetchall()

    backward_map: dict[str, list[str]] = {}
    for source_id, target_id in edge_rows:
        backward_map.setdefault(target_id, []).append(source_id)

    dependents: set[str] = set()
    visited = {decision_id}
    queue = [decision_id]
    while queue:
        current = queue.pop()
        for dep in backward_map.get(current, []):
            if dep not in visited:
                visited.add(dep)
                dependents.add(dep)
                queue.append(dep)

    citing_files = []
    for rel_path in _live_spec_files(repo_root):
        text = (repo_root / rel_path).read_text(encoding="utf-8")
        citations = _extract_citations(text)
        if decision_id in citations:
            citing_files.append(str(rel_path))

    return {
        "decision_id": decision_id,
        "dependent_decisions": sorted(dependents),
        "citing_files": sorted(citing_files),
    }


# --------------------------------------------------------------------------
# R-DRIFT-005: CLI
# --------------------------------------------------------------------------


def _report_value(report, key):
    if isinstance(report, dict):
        return report.get(key)
    return getattr(report, key, None)


def _print_drift_report(report, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report, indent=2))
        return
    entries = _report_value(report, "entries") or []
    if not entries:
        print("No decision drift found.")
        return
    for entry in entries:
        file_ = _report_value(entry, "file")
        cited = _report_value(entry, "cited_decision")
        superseded_by = _report_value(entry, "superseded_by")
        file_commit = _report_value(entry, "file_commit")
        superseder_commit = _report_value(entry, "superseder_ratified_commit")
        print(
            f"{file_}: cites {cited}, superseded by {superseded_by} "
            f"(file last touched at {file_commit}, predates ratification "
            f"{superseder_commit})"
        )


def _print_impact_report(report, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report, indent=2))
        return
    decision_id = _report_value(report, "decision_id")
    dependents = _report_value(report, "dependent_decisions") or []
    citing_files = _report_value(report, "citing_files") or []
    print(f"Impact of altering {decision_id}:")
    if dependents:
        print("  Dependent decisions:")
        for d in dependents:
            print(f"    {d}")
    else:
        print("  Dependent decisions: none")
    if citing_files:
        print("  Citing files:")
        for f in citing_files:
            print(f"    {f}")
    else:
        print("  Citing files: none")


def _default_repo_root() -> Path:
    rc, out, _err = _run_git(Path("."), ["rev-parse", "--show-toplevel"])
    if rc != 0 or not out:
        raise UsageError("not a git repository")
    return Path(out)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if not argv:
        print(
            "usage: hotdocs decision-drift|decision-impact [options]",
            file=sys.stderr,
        )
        return 2

    subcommand = argv[0]
    rest = argv[1:]

    fmt = "text"
    repo_root_arg = None
    positional = []

    for arg in rest:
        if arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
        elif arg.startswith("--repo-root="):
            repo_root_arg = arg.split("=", 1)[1]
        elif arg.startswith("--"):
            print(f"unknown option: {arg}", file=sys.stderr)
            return 2
        else:
            positional.append(arg)

    if fmt not in ("json", "text"):
        print(f"invalid --format: {fmt}", file=sys.stderr)
        return 2

    try:
        if repo_root_arg is not None:
            repo_root = Path(repo_root_arg)
            _check_git_repo(repo_root)
        else:
            repo_root = _default_repo_root()

        if subcommand == "decision-drift":
            report = find_decision_drift(repo_root)
            _print_drift_report(report, fmt)
            return 0
        elif subcommand == "decision-impact":
            if not positional:
                print(
                    "decision-impact requires <decision-id>", file=sys.stderr
                )
                return 2
            decision_id = positional[0]
            report = find_decision_impact(repo_root, decision_id)
            _print_impact_report(report, fmt)
            return 0
        else:
            print(f"unknown subcommand: {subcommand}", file=sys.stderr)
            return 2
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())