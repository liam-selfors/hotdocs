"""
Impact Analyzer (`comp-impact-analyzer`).

Computes the minimal blast radius for a set of changed spec ids, per
`specs/components/impact-analyzer/` (R-IMPACT-001 through R-IMPACT-010).

This module is intentionally a pure, deterministic graph-traversal layer
over corpus state already parsed by `comp-spec-linter` (R-IMPACT-006,
R-IMPACT-009): no network access, no model calls, no dependence on
wall-clock time or execution order. The one external process invoked is
`git`, used strictly read-only to resolve "the prior commit" (R-IMPACT-010)
and to diff specific files against it — never to mutate repository state.

-----------------------------------------------------------------------
Everything below this banner is *this component's own generated code*.
Nothing in this file is copied from, or should be confused with, the
spec text, interface contracts, or dependency contracts that produced
it — those lived only in the prompt that generated this file.
-----------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Dependency loading: comp-spec-linter
#
# `gen/spec-linter/` is a sibling component directory (hyphenated, so it
# cannot be a normal dotted-import target). We first try a plain import in
# case the caller's environment already arranged for it to be importable,
# and otherwise load it directly from its file location. Per this
# pipeline's loading convention, the freshly-created module object MUST be
# registered in `sys.modules` under its load-time name *before*
# `exec_module` runs — `spec_linter` defines dataclasses, and a
# dataclass's own internals look up `sys.modules[cls.__module__]` while its
# class body executes, which would crash if the module weren't registered
# yet.
# ---------------------------------------------------------------------------

def _load_dependency_module(module_name: str, component_dirname: str) -> Any:
    if module_name in sys.modules:
        return sys.modules[module_name]

    try:
        return importlib.import_module(module_name)
    except ImportError:
        pass

    gen_root = Path(__file__).resolve().parent.parent
    base = gen_root / component_dirname

    flat_candidate = base / f"{module_name}.py"
    pkg_candidate = base / module_name / "__init__.py"

    if flat_candidate.exists():
        spec = importlib.util.spec_from_file_location(module_name, flat_candidate)
    elif pkg_candidate.exists():
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_candidate,
            submodule_search_locations=[str(pkg_candidate.parent)],
        )
    else:
        raise ImportError(
            f"could not locate dependency module {module_name!r} under {base}"
        )

    if spec is None or spec.loader is None:
        raise ImportError(f"could not build a module spec for {module_name!r}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


spec_linter = _load_dependency_module("spec_linter", "spec-linter")


# ---------------------------------------------------------------------------
# Public data shapes — interface/data/BlastRadiusReport.md
# ---------------------------------------------------------------------------

_REASON_ORDER = {
    "direct": 0,
    "transitive-interface": 1,
    "transitive-var": 2,
    "transitive-capability": 3,
    "transitive-guarantee": 4,
}


@dataclass
class ImpactedEntry:
    component_id: str
    reason: str
    via: Optional[str] = None
    guarantee_ids: Optional[List[str]] = None

    def to_dict(self) -> dict:
        d: Dict[str, Any] = {
            "component_id": self.component_id,
            "reason": self.reason,
            "via": self.via,
        }
        if self.guarantee_ids is not None:
            d["guarantee_ids"] = list(self.guarantee_ids)
        return d


@dataclass
class BlastRadiusReport:
    impacted: List[ImpactedEntry] = field(default_factory=list)
    precondition_error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "impacted": [e.to_dict() for e in self.impacted],
            "precondition_error": self.precondition_error,
        }


# ---------------------------------------------------------------------------
# git helpers — R-IMPACT-010: "the prior commit" == merge-base(HEAD, default
# branch); per-file change detection is a real content comparison against
# that commit, never inferred from an id's shape.
# ---------------------------------------------------------------------------

def _run_git(repo_root: Path, args: List[str], text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=text)


def _git_repo_root(start: Path) -> Path:
    out = _run_git(start, ["rev-parse", "--show-toplevel"])
    if out.returncode != 0:
        raise RuntimeError(
            f"could not determine git repository root from {start}: {out.stderr.strip()}"
        )
    return Path(out.stdout.strip())


def _resolve_default_branch_ref(repo_root: Path) -> str:
    out = _run_git(repo_root, ["symbolic-ref", "refs/remotes/origin/HEAD"])
    if out.returncode == 0 and out.stdout.strip():
        return out.stdout.strip()
    for candidate in ("origin/main", "origin/master", "main", "master"):
        check = _run_git(repo_root, ["rev-parse", "--verify", "--quiet", candidate])
        if check.returncode == 0:
            return candidate
    raise RuntimeError(
        "unable to determine the repository's default branch for merge-base resolution"
    )


def _merge_base(repo_root: Path, ref: str) -> str:
    out = _run_git(repo_root, ["merge-base", "HEAD", ref])
    if out.returncode != 0:
        raise RuntimeError(
            f"git merge-base failed for HEAD..{ref}: {out.stderr.strip()}"
        )
    return out.stdout.strip()


def _file_changed(repo_root: Path, rel_path: str, merge_base_sha: str) -> bool:
    old = _run_git(repo_root, ["show", f"{merge_base_sha}:{rel_path}"], text=False)
    old_exists = old.returncode == 0
    new_path = repo_root / rel_path
    new_exists = new_path.exists()
    if old_exists != new_exists:
        return True
    if not old_exists and not new_exists:
        return False
    new_bytes = new_path.read_bytes()
    return old.stdout != new_bytes


def _list_git_files_in_dir(repo_root: Path, rel_dir: str, sha: str) -> Set[str]:
    out = _run_git(repo_root, ["ls-tree", "-r", "--name-only", sha, "--", rel_dir])
    if out.returncode != 0:
        return set()
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def _list_fs_files_in_dir(repo_root: Path, rel_dir: str) -> Set[str]:
    d = repo_root / rel_dir
    if not d.exists():
        return set()
    result: Set[str] = set()
    for p in d.rglob("*"):
        if p.is_file():
            result.add(str(p.relative_to(repo_root)).replace("\\", "/"))
    return result


def _dir_changed_files(repo_root: Path, rel_dir: str, sha: str) -> Set[str]:
    """Files added, removed, or content-changed under `rel_dir`, compared
    independently (R-IMPACT-003/008: "a file added or removed counts as
    changed")."""
    old_files = _list_git_files_in_dir(repo_root, rel_dir, sha)
    new_files = _list_fs_files_in_dir(repo_root, rel_dir)
    changed: Set[str] = set()
    for f in old_files | new_files:
        if _file_changed(repo_root, f, sha):
            changed.add(f)
    return changed


# ---------------------------------------------------------------------------
# Corpus-graph helpers, built on top of comp-spec-linter's already-parsed
# Corpus (R-IMPACT-009's node/edge kinds, expressed here over the Corpus
# object comp-spec-linter already builds from the shared graph-query
# engine's `nodes`/`edges` views).
# ---------------------------------------------------------------------------

def _resolve_changed_id(spec_id: str, corpus: Any) -> Optional[Tuple[str, str]]:
    """Classify one `--changed` id and resolve it to the thing R-IMPACT-001/
    004/005 actually need: either an owning component id ("component"), a
    changed var declaration id ("var"), or a changed capability id
    ("capability"). Returns None if the id does not exist in the corpus at
    all (a usage error, per the CLI's exit code 2)."""
    if spec_id.startswith("comp-"):
        slug = spec_id[len("comp-"):]
        if slug in corpus.components:
            return ("component", spec_id)
        return None

    doc = corpus.id_index.get(spec_id)
    if doc is None:
        return None

    if spec_id.startswith("P-"):
        return ("capability", spec_id)
    if spec_id.startswith("VAR-"):
        return ("var", spec_id)

    component = getattr(doc, "component", None)
    if component:
        return ("component", f"comp-{component}")

    return None


def _find_guarantee_owner(gid: str, corpus: Any) -> Optional[str]:
    """D65: a G-id's owning component is determined by which component's
    real `interface/guarantees/` directory actually contains a file with
    that id — never parsed out of the id string itself."""
    for slug, comp in corpus.components.items():
        guarantees = getattr(comp, "interface_guarantees", None) or {}
        for key, doc in guarantees.items():
            if key == gid:
                return f"comp-{slug}"
            doc_path = getattr(doc, "path", None)
            if doc_path is not None and doc_path.stem == gid:
                return f"comp-{slug}"
    return None


def _build_edge_maps(
    corpus: Any,
) -> Tuple[
    Dict[str, Set[str]],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
    Dict[str, Dict[str, Set[str]]],
]:
    """Reverse-edge maps used for one-hop propagation (R-IMPACT-003/004/
    005/008), built from each component's root frontmatter.

    - depends_on_map[upstream_id] -> dependents (R-IMPACT-003/008)
    - uses_var_map[var_id] -> dependents (R-IMPACT-004)
    - realizes_map[capability_id] -> dependents (R-IMPACT-005)
    - depends_on_guarantees_map[dependent_id][upstream_id] -> declared G-ids
      (R-IMPACT-008's opt-in narrowing; D65's flat-list frontmatter shape)
    """
    depends_on_map: Dict[str, Set[str]] = {}
    uses_var_map: Dict[str, Set[str]] = {}
    realizes_map: Dict[str, Set[str]] = {}
    depends_on_guarantees_map: Dict[str, Dict[str, Set[str]]] = {}

    for slug, comp in corpus.components.items():
        full_id = f"comp-{slug}"
        root = getattr(comp, "root", None)
        fm = root.frontmatter if root is not None else {}
        fm = fm or {}

        for dep in (fm.get("depends_on") or []):
            depends_on_map.setdefault(dep, set()).add(full_id)

        for var in (fm.get("uses_var") or []):
            uses_var_map.setdefault(var, set()).add(full_id)

        for p in (fm.get("realizes") or []):
            realizes_map.setdefault(p, set()).add(full_id)

        declared = fm.get("depends_on_guarantees") or []
        for gid in declared:
            owner = _find_guarantee_owner(gid, corpus)
            if owner is not None:
                depends_on_guarantees_map.setdefault(full_id, {}).setdefault(
                    owner, set()
                ).add(gid)

    return depends_on_map, uses_var_map, realizes_map, depends_on_guarantees_map


def _format_precondition_error(fail_findings: List[Any]) -> str:
    details = "; ".join(
        f"{f.rule_id} ({f.file}:{f.line}): {f.message}" for f in fail_findings
    )
    return (
        f"corpus did not pass spec-linter cleanly "
        f"({len(fail_findings)} fail-severity finding(s)): {details}"
    )


def _dedupe_and_sort(entries: List[ImpactedEntry]) -> List[ImpactedEntry]:
    seen: Dict[Tuple[Any, ...], ImpactedEntry] = {}
    for e in entries:
        key = (
            e.component_id,
            e.reason,
            e.via,
            tuple(sorted(e.guarantee_ids)) if e.guarantee_ids else None,
        )
        seen[key] = e
    result = list(seen.values())
    result.sort(
        key=lambda e: (
            e.component_id,
            _REASON_ORDER.get(e.reason, 99),
            e.via or "",
        )
    )
    return result


# ---------------------------------------------------------------------------
# Library entry point — interface/library.md
# ---------------------------------------------------------------------------

def compute_blast_radius(changed_ids: List[str], repo_root: Path) -> BlastRadiusReport:
    """Pure function over the filesystem state at `repo_root`
    (R-IMPACT-006): no network access, no model calls, no side effects.

    Raises `ValueError` if `changed_ids` is empty or contains an id that
    does not exist anywhere in the corpus (the library-level analogue of
    the CLI's exit code 2).
    """
    if not changed_ids:
        raise ValueError("changed_ids must contain at least one spec id")

    repo_root = Path(repo_root)
    corpus = spec_linter.load_corpus(repo_root)

    component_direct: Set[str] = set()
    var_changed: Set[str] = set()
    cap_changed: Set[str] = set()

    for sid in changed_ids:
        resolved = _resolve_changed_id(sid, corpus)
        if resolved is None:
            raise ValueError(f"unknown spec id: {sid!r}")
        kind, cid = resolved
        if kind == "component":
            component_direct.add(cid)
        elif kind == "var":
            var_changed.add(cid)
        elif kind == "capability":
            cap_changed.add(cid)

    # R-IMPACT-007: fail closed if the corpus is not spec-linter clean.
    lint_report = spec_linter.lint(None, repo_root)
    fail_findings = [f for f in lint_report.findings if f.severity == "fail"]
    if fail_findings:
        return BlastRadiusReport(
            impacted=[], precondition_error=_format_precondition_error(fail_findings)
        )

    (
        depends_on_map,
        uses_var_map,
        realizes_map,
        depends_on_guarantees_map,
    ) = _build_edge_maps(corpus)

    entries: List[ImpactedEntry] = []

    # R-IMPACT-001: every directly-changed component, regardless of which
    # file within its bundle changed.
    for cid in component_direct:
        entries.append(ImpactedEntry(component_id=cid, reason="direct", via=None))

    merge_base_sha: Optional[str] = None
    if component_direct:
        default_ref = _resolve_default_branch_ref(repo_root)
        merge_base_sha = _merge_base(repo_root, default_ref)

    for changed_comp in component_direct:
        slug = changed_comp[len("comp-"):]
        if slug not in corpus.components:
            continue
        comp_dir = f"specs/components/{slug}"

        # R-IMPACT-002/003: cli.md, library.md, data/* always propagate in
        # full when they changed; component.md/requirements/constraints/
        # acceptance changing alone never does.
        interface_changed = (
            _file_changed(repo_root, f"{comp_dir}/interface/cli.md", merge_base_sha)
            or _file_changed(repo_root, f"{comp_dir}/interface/library.md", merge_base_sha)
            or bool(_dir_changed_files(repo_root, f"{comp_dir}/interface/data", merge_base_sha))
        )
        if interface_changed:
            for dependent in depends_on_map.get(changed_comp, ()):
                entries.append(
                    ImpactedEntry(
                        component_id=dependent,
                        reason="transitive-interface",
                        via=changed_comp,
                    )
                )

        # R-IMPACT-008: interface/guarantees/*, narrowed by an opt-in,
        # non-empty depends_on_guarantees declaration naming this upstream.
        changed_guarantee_files = _dir_changed_files(
            repo_root, f"{comp_dir}/interface/guarantees", merge_base_sha
        )
        if changed_guarantee_files:
            changed_gids = {Path(f).stem for f in changed_guarantee_files}
            for dependent in depends_on_map.get(changed_comp, ()):
                narrow = depends_on_guarantees_map.get(dependent, {}).get(changed_comp)
                if narrow:
                    matched = sorted(narrow & changed_gids)
                    if matched:
                        entries.append(
                            ImpactedEntry(
                                component_id=dependent,
                                reason="transitive-guarantee",
                                via=changed_comp,
                                guarantee_ids=matched,
                            )
                        )
                else:
                    entries.append(
                        ImpactedEntry(
                            component_id=dependent,
                            reason="transitive-guarantee",
                            via=changed_comp,
                            guarantee_ids=sorted(changed_gids),
                        )
                    )

    # R-IMPACT-004: changed specs/vars/ declarations.
    for var_id in var_changed:
        for dependent in uses_var_map.get(var_id, ()):
            entries.append(
                ImpactedEntry(component_id=dependent, reason="transitive-var", via=var_id)
            )

    # R-IMPACT-005: changed product capabilities.
    for p_id in cap_changed:
        for dependent in realizes_map.get(p_id, ()):
            entries.append(
                ImpactedEntry(
                    component_id=dependent, reason="transitive-capability", via=p_id
                )
            )

    return BlastRadiusReport(impacted=_dedupe_and_sort(entries), precondition_error=None)


# ---------------------------------------------------------------------------
# CLI — interface/cli.md
# ---------------------------------------------------------------------------

def _format_text(report: BlastRadiusReport) -> str:
    if report.precondition_error:
        return f"precondition error: {report.precondition_error}"
    if not report.impacted:
        return "no components impacted"
    lines = []
    for entry in report.impacted:
        if entry.reason == "direct":
            lines.append(f"{entry.component_id}: direct")
        elif entry.reason == "transitive-guarantee":
            gids = ",".join(entry.guarantee_ids or [])
            lines.append(f"{entry.component_id}: {entry.reason} via {entry.via} [{gids}]")
        else:
            lines.append(f"{entry.component_id}: {entry.reason} via {entry.via}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs impact", add_help=True)
    parser.add_argument("--changed", nargs="+", default=None, metavar="SPEC_ID")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")

    args_list = sys.argv[1:] if argv is None else argv

    try:
        args = parser.parse_args(args_list)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        return code

    if not args.changed:
        print("error: --changed requires at least one spec id", file=sys.stderr)
        return 2

    try:
        repo_root = Path(args.repo_root) if args.repo_root else _git_repo_root(Path.cwd())
    except Exception as exc:  # noqa: BLE001 - surfaced as a usage/environment error
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        report = compute_blast_radius(list(args.changed), repo_root)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - e.g. git/merge-base resolution failure
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_format_text(report))

    if report.precondition_error:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())