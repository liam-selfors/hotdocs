import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import duckdb

CITATION_PATTERN = re.compile(r"\bD\d+\b")

_MODULE_CACHE: Dict[Tuple[str, str], object] = {}


@dataclass
class DriftEntry:
    file: str
    cited_decision: str
    superseded_by: str
    file_commit: str
    superseder_ratified_commit: str


@dataclass
class DriftReport:
    entries: List[DriftEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DecisionImpactReport:
    decision_id: str
    dependent_decisions: List[str] = field(default_factory=list)
    citing_files: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _load_graph_query_engine(repo_root: Path):
    repo_root = Path(repo_root)
    module_name = "graph_query_engine"
    cache_key = (str(repo_root), module_name)
    cached = _MODULE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    base = repo_root / "gen" / "graph-query-engine"
    flat_path = base / "graph_query_engine.py"
    pkg_init = base / "graph_query_engine" / "__init__.py"

    if flat_path.is_file():
        module_path = flat_path
        submodule_search_locations = None
    elif pkg_init.is_file():
        module_path = pkg_init
        submodule_search_locations = [str(pkg_init.parent)]
    else:
        raise RuntimeError(f"graph_query_engine module not found under {base}")

    spec = importlib.util.spec_from_file_location(
        module_name,
        module_path,
        submodule_search_locations=submodule_search_locations,
    )
    module = importlib.util.module_from_spec(spec)
    # Must register in sys.modules before exec_module: dataclasses defined in
    # the loaded module resolve their own __module__ via sys.modules at
    # class-body-execution time.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[cache_key] = module
    return module


def _load_graph_data(repo_root: Path) -> Tuple[List[Tuple[str, str, str]], Dict[str, Optional[str]]]:
    module = _load_graph_query_engine(repo_root)
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        module.load_views(con, Path(repo_root))
        edges = con.execute("SELECT source_id, target_id, edge_type FROM edges").fetchall()
        lineage_rows = con.execute(
            "SELECT id, last_ratified_commit FROM decision_lineage"
        ).fetchall()
    finally:
        con.close()
    lineage_map = {row[0]: row[1] for row in lineage_rows}
    return edges, lineage_map


def _check_git_repo(repo_root: Path) -> None:
    repo_root = Path(repo_root)
    if not repo_root.is_dir():
        raise RuntimeError(f"repo_root is not a readable directory: {repo_root}")
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise RuntimeError(f"not a git repository: {repo_root}")


def _last_commit_for_file(repo_root: Path, rel_path: str) -> str:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", rel_path],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed for {rel_path}: {result.stderr.strip()}")
    commit = result.stdout.strip()
    if not commit:
        raise RuntimeError(f"no commit history for {rel_path} (uncommitted?)")
    return commit


def _is_ancestor(repo_root: Path, maybe_ancestor: str, commit: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", maybe_ancestor, commit],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _live_spec_files(repo_root: Path) -> List[Path]:
    specs_dir = Path(repo_root) / "specs"
    if not specs_dir.is_dir():
        return []
    decisions_dir = specs_dir / "decisions"
    files = []
    for path in specs_dir.rglob("*.md"):
        try:
            path.relative_to(decisions_dir)
            continue
        except ValueError:
            pass
        files.append(path)
    return sorted(files)


def _latest_decision(
    repo_root: Path, candidates: Sequence[str], lineage_map: Dict[str, Optional[str]]
) -> str:
    best = candidates[0]
    for cand in candidates[1:]:
        best_commit = lineage_map.get(best)
        cand_commit = lineage_map.get(cand)
        if not best_commit or not cand_commit:
            continue
        if _is_ancestor(repo_root, best_commit, cand_commit):
            best = cand
    return best


def _find_terminal_superseder(
    repo_root: Path,
    edges: Sequence[Tuple[str, str, str]],
    lineage_map: Dict[str, Optional[str]],
    start: str,
) -> Optional[str]:
    target_to_sources: Dict[str, Set[str]] = {}
    for source_id, target_id, edge_type in edges:
        if edge_type == "supersedes":
            target_to_sources.setdefault(target_id, set()).add(source_id)

    visited = {start}
    current = start
    result = None
    while True:
        candidates = sorted(target_to_sources.get(current, set()) - visited)
        if not candidates:
            break
        nxt = candidates[0] if len(candidates) == 1 else _latest_decision(
            repo_root, candidates, lineage_map
        )
        visited.add(nxt)
        result = nxt
        current = nxt
    return result


def find_decision_drift(repo_root: Path) -> DriftReport:
    repo_root = Path(repo_root)
    _check_git_repo(repo_root)
    edges, lineage_map = _load_graph_data(repo_root)

    entries: List[DriftEntry] = []
    for path in _live_spec_files(repo_root):
        text = path.read_text()
        citations = sorted(set(CITATION_PATTERN.findall(text)))
        if not citations:
            continue
        rel_path = str(path.relative_to(repo_root))
        file_commit: Optional[str] = None
        for cited in citations:
            superseder = _find_terminal_superseder(repo_root, edges, lineage_map, cited)
            if superseder is None:
                continue
            superseder_commit = lineage_map.get(superseder)
            if not superseder_commit:
                continue
            if file_commit is None:
                file_commit = _last_commit_for_file(repo_root, rel_path)
            if _is_ancestor(repo_root, file_commit, superseder_commit):
                entries.append(
                    DriftEntry(
                        file=rel_path,
                        cited_decision=cited,
                        superseded_by=superseder,
                        file_commit=file_commit,
                        superseder_ratified_commit=superseder_commit,
                    )
                )

    entries.sort(key=lambda e: (e.file, e.cited_decision))
    return DriftReport(entries=entries)


def find_decision_impact(repo_root: Path, decision_id: str) -> DecisionImpactReport:
    repo_root = Path(repo_root)
    _check_git_repo(repo_root)
    edges, _lineage_map = _load_graph_data(repo_root)

    target_to_sources: Dict[str, Set[str]] = {}
    for source_id, target_id, edge_type in edges:
        if edge_type in ("supersedes", "builds_on"):
            target_to_sources.setdefault(target_id, set()).add(source_id)

    dependent: Set[str] = set()
    visited = {decision_id}
    frontier = [decision_id]
    while frontier:
        current = frontier.pop()
        for source_id in target_to_sources.get(current, set()):
            if source_id not in visited:
                visited.add(source_id)
                dependent.add(source_id)
                frontier.append(source_id)

    citing_files = []
    for path in _live_spec_files(repo_root):
        text = path.read_text()
        if decision_id in set(CITATION_PATTERN.findall(text)):
            citing_files.append(str(path.relative_to(repo_root)))

    return DecisionImpactReport(
        decision_id=decision_id,
        dependent_decisions=sorted(dependent),
        citing_files=sorted(citing_files),
    )


def _print_drift_report(report: DriftReport, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
        return
    if not report.entries:
        print("No decision drift detected.")
        return
    for entry in report.entries:
        print(
            f"{entry.file}: cites {entry.cited_decision}, superseded by "
            f"{entry.superseded_by} (file commit {entry.file_commit} predates "
            f"ratification {entry.superseder_ratified_commit})"
        )


def _print_impact_report(report: DecisionImpactReport, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
        return
    print(f"Decision {report.decision_id}:")
    print(f"  dependent decisions: {', '.join(report.dependent_decisions) or '(none)'}")
    print("  citing files:")
    if report.citing_files:
        for file in report.citing_files:
            print(f"    {file}")
    else:
        print("    (none)")


def _default_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("not a git repository")
    return Path(result.stdout.strip())


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(
            "usage: hotdocs decision-drift|decision-impact <decision-id> "
            "[--format=json|text] [--repo-root=<dir>]",
            file=sys.stderr,
        )
        return 2

    subcommand = argv[0]
    rest = argv[1:]
    if subcommand not in ("decision-drift", "decision-impact"):
        print(f"unknown subcommand: {subcommand}", file=sys.stderr)
        return 2

    fmt = "text"
    repo_root_arg: Optional[str] = None
    positional: List[str] = []
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
            if not repo_root.is_dir():
                print(f"unreadable --repo-root: {repo_root_arg}", file=sys.stderr)
                return 2
        else:
            repo_root = _default_repo_root()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        if subcommand == "decision-drift":
            report = find_decision_drift(repo_root)
            _print_drift_report(report, fmt)
        else:
            if not positional:
                print("decision-impact requires <decision-id>", file=sys.stderr)
                return 2
            decision_id = positional[0]
            impact_report = find_decision_impact(repo_root, decision_id)
            _print_impact_report(impact_report, fmt)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())