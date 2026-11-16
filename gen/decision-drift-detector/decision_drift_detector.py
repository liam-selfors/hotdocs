"""Decision Drift Detector.

Flags live spec files whose ``D<N>`` citations point at a decision that has
since been superseded by a decision ratified after the citing file's own last
commit (R-DRIFT-001/002), and reports what would be affected by altering a
given decision (R-DRIFT-003). Purely diagnostic: never a gate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import duckdb

CITATION_RE = re.compile(r"\bD\d+\b")

_GQE_SLUG = "graph-query-engine"
_GQE_MODULE = "graph_query_engine"

_MODULE_CACHE: dict = {}


class DecisionDriftError(Exception):
    """A usage error: not a git repository, or a cited file with no history."""


# ---------------------------------------------------------------------------
# Dependency resolution (R-DRIFT-004)
# ---------------------------------------------------------------------------


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load_dependency(repo_root, slug: str, module_name: str):
    key = (str(repo_root), module_name)
    if key in _MODULE_CACHE:
        return _MODULE_CACHE[key]
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    digest = hashlib.sha1(str(base.resolve()).encode("utf-8")).hexdigest()[:16]
    load_name = f"_decision_drift_dep_{module_name}_{digest}"
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(load_name, flat)
    else:
        pkg_dir = base / module_name
        spec = importlib.util.spec_from_file_location(
            load_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[key] = module
    return module


def _open_views(root: Path):
    gqe = _load_dependency(root, _GQE_SLUG, _GQE_MODULE)
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    gqe.load_views(con, root)
    return con


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
    )


def _require_git_repo(root: Path) -> None:
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise DecisionDriftError(f"not a git repository: {root}")


def _default_repo_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise DecisionDriftError("not a git repository (no --repo-root given)")
    return Path(proc.stdout.strip())


def _file_commit(root: Path, rel: str) -> str:
    out = _git(root, "log", "-1", "--format=%H", "--", rel).stdout.strip()
    if not out:
        raise DecisionDriftError(f"cited file has no commit history: {rel}")
    return out


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", older, newer).returncode == 0


# ---------------------------------------------------------------------------
# Corpus helpers
# ---------------------------------------------------------------------------


def _decision_key(decision_id: str):
    return (len(decision_id), decision_id)


def _live_citations(root: Path) -> list:
    """Return [(relative_posix_path, [cited D-ids sorted])] for every live spec file."""
    result = []
    for path in sorted((root / "specs").rglob("*.md")):
        rel = path.relative_to(root)
        if rel.parts[:2] == ("specs", "decisions"):
            continue
        text = path.read_text(encoding="utf-8")
        cites = sorted(set(CITATION_RE.findall(text)), key=_decision_key)
        result.append((rel.as_posix(), cites))
    return result


def _edge_map(con, edge_types: tuple, reverse: bool) -> dict:
    placeholders = ", ".join("?" for _ in edge_types)
    rows = con.execute(
        f"SELECT source_id, target_id FROM edges WHERE edge_type IN ({placeholders})",
        list(edge_types),
    ).fetchall()
    mapping: dict = {}
    for source_id, target_id in rows:
        key, value = (target_id, source_id) if reverse else (source_id, target_id)
        mapping.setdefault(key, set()).add(value)
    return mapping


def _closure(start: str, mapping: dict) -> set:
    seen: set = set()
    stack = [start]
    while stack:
        current = stack.pop()
        for nxt in mapping.get(current, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    seen.discard(start)
    return seen


def _latest_superseder(root: Path, cited: str, superseded_by: dict, ratified: dict):
    candidates = sorted(
        (d for d in _closure(cited, superseded_by) if d in ratified),
        key=_decision_key,
    )
    latest = None
    for decision in candidates:
        if latest is None or _is_ancestor(root, ratified[latest], ratified[decision]):
            latest = decision
    return latest


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def find_decision_drift(repo_root: Path) -> dict:
    root = Path(repo_root)
    _require_git_repo(root)
    con = _open_views(root)
    try:
        # supersedes edge: source_id is the newer decision, target_id the older.
        superseded_by = _edge_map(con, ("supersedes",), reverse=True)
        ratified = dict(
            con.execute(
                "SELECT id, last_ratified_commit FROM decision_lineage "
                "WHERE last_ratified_commit IS NOT NULL"
            ).fetchall()
        )
    finally:
        con.close()

    entries = []
    for rel, cites in _live_citations(root):
        for cited in cites:
            superseder = _latest_superseder(root, cited, superseded_by, ratified)
            if superseder is None:
                continue
            file_commit = _file_commit(root, rel)
            superseder_commit = ratified[superseder]
            if _is_ancestor(root, file_commit, superseder_commit):
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
    root = Path(repo_root)
    con = _open_views(root)
    try:
        dependents_of = _edge_map(con, ("supersedes", "builds_on"), reverse=True)
    finally:
        con.close()

    dependent_decisions = sorted(_closure(decision_id, dependents_of), key=_decision_key)
    citing_files = [rel for rel, cites in _live_citations(root) if decision_id in cites]
    return {
        "decision_id": decision_id,
        "dependent_decisions": dependent_decisions,
        "citing_files": citing_files,
    }


# ---------------------------------------------------------------------------
# Rendering / CLI (R-DRIFT-005)
# ---------------------------------------------------------------------------


def _render_drift_text(report: dict) -> str:
    lines = [
        f"{e['file']}: cites {e['cited_decision']}, superseded by {e['superseded_by']} "
        f"(file commit {e['file_commit']} predates ratification "
        f"{e['superseder_ratified_commit']})"
        for e in report["entries"]
    ]
    return "\n".join(lines) or "No decision drift candidates found."


def _render_impact_text(report: dict) -> str:
    dependents = ", ".join(report["dependent_decisions"]) or "none"
    files = "\n".join(f"  {f}" for f in report["citing_files"]) or "  (none)"
    return (
        f"Decision: {report['decision_id']}\n"
        f"Dependent decisions: {dependents}\n"
        f"Citing files:\n{files}"
    )


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=("json", "text"), default="text")
    common.add_argument("--repo-root", default=None)

    parser = argparse.ArgumentParser(prog="hotdocs")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("decision-drift", parents=[common])
    impact = sub.add_parser("decision-impact", parents=[common])
    impact.add_argument("decision_id")
    return parser


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code

    try:
        root = _default_repo_root() if args.repo_root is None else Path(args.repo_root)
        _require_git_repo(root)
        if args.command == "decision-drift":
            report = find_decision_drift(root)
            text = _render_drift_text
        else:
            report = find_decision_impact(root, args.decision_id)
            text = _render_impact_text
    except DecisionDriftError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))