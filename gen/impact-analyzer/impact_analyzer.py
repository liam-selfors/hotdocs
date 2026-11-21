"""impact-analyzer: computes the blast radius of a set of changed spec ids."""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = "usage: hotdocs impact --changed <spec-id>... [--repo-root=<dir>] [--format=json|text]"


# --------------------------------------------------------------------------
# Report types
# --------------------------------------------------------------------------


@dataclass
class ImpactedComponent:
    component_id: str
    reason: str
    via: object = None
    guarantee_ids: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self) -> dict:
        d = {"component_id": self.component_id, "reason": self.reason, "via": self.via}
        if self.reason == "transitive-guarantee":
            d["guarantee_ids"] = list(self.guarantee_ids)
        return d


@dataclass
class BlastRadiusReport:
    impacted: list = field(default_factory=list)
    precondition_error: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self) -> dict:
        return {
            "impacted": [e.to_dict() for e in self.impacted],
            "precondition_error": self.precondition_error,
        }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    return [value] if value else []


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_spec_linter(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / "spec-linter"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "spec-linter"
    pkg_init = dep_dir / "spec_linter" / "__init__.py"
    if pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            "spec_linter", pkg_init, submodule_search_locations=[str(pkg_init.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location("spec_linter", dep_dir / "spec_linter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo_root: Path, *args):
    proc = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True)
    if proc.returncode != 0:
        return None
    return proc.stdout


def _prior_commit(repo_root: Path):
    branch = None
    out = _git(repo_root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    if out is not None and out.strip():
        branch = out.decode().strip()
    else:
        for ref in ("refs/heads/main", "refs/heads/master"):
            if _git(repo_root, "rev-parse", "--verify", "-q", ref) is not None:
                branch = ref
                break
    if branch is None:
        return None
    out = _git(repo_root, "merge-base", "HEAD", branch)
    if out is None or not out.strip():
        return None
    return out.decode().strip()


def _base_files(repo_root: Path, base, reldir: str) -> dict:
    if base is None:
        return {}
    out = _git(repo_root, "ls-tree", "-r", "-z", "--name-only", base, "--", reldir)
    files = {}
    if out is None:
        return files
    for name in out.decode().split("\0"):
        if name:
            files[name] = _git(repo_root, "cat-file", "blob", f"{base}:./{name}")
    return files


def _work_files(repo_root: Path, reldir: str) -> dict:
    root = Path(repo_root)
    files = {}
    for p in sorted((root / reldir).rglob("*")):
        if p.is_file():
            files[p.relative_to(root).as_posix()] = p.read_bytes()
    return files


def _changed(base: dict, work: dict, select) -> list:
    keys = sorted(k for k in set(base) | set(work) if select(k))
    return [k for k in keys if base.get(k) != work.get(k)]


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------


def _analyze(changed_ids, repo_root: Path):
    repo_root = Path(repo_root)
    linter = _load_spec_linter(repo_root)
    lint_report = linter.lint(None, repo_root)
    fails = [f for f in (_get(lint_report, "findings") or []) if _get(f, "severity") == "fail"]
    if fails:
        msg = f"corpus is not lint-clean: {len(fails)} fail-severity finding(s)"
        return BlastRadiusReport(impacted=[], precondition_error=msg), None

    corpus = linter.load_corpus(repo_root)
    docs = _get(corpus, "docs") or []
    known = set(_get(corpus, "id_index") or {})
    var_ids, cap_ids = set(), set()
    for doc in docs:
        doc_id = _get(doc, "doc_id")
        known.add(doc_id)
        doc_type = _get(doc, "doc_type")
        if doc_type == "var":
            var_ids.add(doc_id)
        elif doc_type == "product":
            cap_ids.add(doc_id)

    comps = {}  # component id -> (slug, frontmatter)
    owner = {}  # G-id -> owning component id
    for slug, comp in sorted((_get(corpus, "components") or {}).items()):
        root = _get(comp, "root")
        if root is None:
            continue
        fm = _get(root, "frontmatter") or {}
        cid = _get(fm, "id")
        comps[cid] = (slug, fm)
        for gid in _get(comp, "interface_guarantees") or {}:
            owner[gid] = cid

    changed = sorted(set(changed_ids))
    direct = [c for c in changed if c in comps]
    base = _prior_commit(repo_root)

    def dependents(key, target):
        return sorted(c for c, (_, fm) in comps.items() if target in _as_list(_get(fm, key)))

    found = {}
    for cid in direct:
        slug = comps[cid][0]
        cdir = f"specs/components/{slug}/interface"
        base_files = _base_files(repo_root, base, cdir)
        work_files = _work_files(repo_root, cdir)

        def is_interface(path, cdir=cdir):
            return path in (f"{cdir}/cli.md", f"{cdir}/library.md") or path.startswith(f"{cdir}/data/")

        def is_guarantee(path, cdir=cdir):
            parent, _, name = path.rpartition("/")
            return parent == f"{cdir}/guarantees" and fnmatch.fnmatchcase(name, "G-*.md")

        deps = dependents("depends_on", cid)
        if _changed(base_files, work_files, is_interface):
            for dep in deps:
                found.setdefault(dep, ImpactedComponent(dep, "transitive-interface", cid))
        changed_g = sorted(
            Path(p).stem for p in _changed(base_files, work_files, is_guarantee)
        )
        if changed_g:
            for dep in deps:
                declared = [
                    g for g in _as_list(_get(comps[dep][1], "depends_on_guarantees"))
                    if owner.get(g) == cid
                ]
                if declared:
                    hit = sorted(set(declared) & set(changed_g))
                    if hit:
                        found.setdefault(
                            dep, ImpactedComponent(dep, "transitive-guarantee", cid, hit)
                        )
                else:
                    found.setdefault(
                        dep, ImpactedComponent(dep, "transitive-guarantee", cid, list(changed_g))
                    )

    for vid in (v for v in changed if v in var_ids):
        for dep in dependents("uses_var", vid):
            found.setdefault(dep, ImpactedComponent(dep, "transitive-var", vid))

    for pid in (p for p in changed if p in cap_ids):
        for dep in dependents("realizes", pid):
            found.setdefault(dep, ImpactedComponent(dep, "transitive-capability", pid))

    impacted = [ImpactedComponent(c, "direct", None) for c in direct]
    impacted += [found[c] for c in sorted(found) if c not in direct]
    return BlastRadiusReport(impacted=impacted, precondition_error=None), known


def compute_blast_radius(changed_ids: list, repo_root: Path) -> BlastRadiusReport:
    return _analyze(changed_ids, repo_root)[0]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse(argv: list) -> tuple:
    changed, repo_root, fmt = [], None, "text"
    i = 0
    n = len(argv)

    def take_ids(j):
        while j < n and not argv[j].startswith("-"):
            changed.append(argv[j])
            j += 1
        return j

    while i < n:
        tok = argv[i]
        if tok == "--changed":
            if i + 1 >= n:
                raise _UsageError("--changed requires a value")
            i = take_ids(i + 1)
            continue
        if tok.startswith("--changed="):
            changed.append(tok[len("--changed="):])
            i = take_ids(i + 1)
            continue
        if tok in ("--repo-root", "--format"):
            if i + 1 >= n:
                raise _UsageError(f"{tok} requires a value")
            name, value = tok, argv[i + 1]
            i += 2
        elif tok.startswith("--repo-root=") or tok.startswith("--format="):
            name, _, value = tok.partition("=")
            i += 1
        else:
            raise _UsageError(f"unknown argument: {tok}")
        if name == "--repo-root":
            repo_root = value
        else:
            if value not in ("json", "text"):
                raise _UsageError(f"invalid --format value: {value}")
            fmt = value
    if not changed:
        raise _UsageError("no --changed ids given")
    return changed, repo_root, fmt


def _default_repo_root() -> Path:
    out = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if out is None:
        return Path.cwd()
    return Path(out.decode().strip())


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _text(report: BlastRadiusReport) -> str:
    if report.precondition_error is not None:
        return f"precondition error: {report.precondition_error}"
    if not report.impacted:
        return "no components impacted"
    lines = []
    for e in report.impacted:
        parts = [e.component_id, e.reason]
        if e.via is not None:
            parts.append(f"via {e.via}")
        if e.reason == "transitive-guarantee":
            parts.append(",".join(e.guarantee_ids))
        lines.append("\t".join(parts))
    return "\n".join(lines)


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        changed, repo_root, fmt = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(str(exc))
    root = Path(repo_root) if repo_root is not None else _default_repo_root()
    report, known = _analyze(changed, root)
    if report.precondition_error is None:
        unknown = sorted(c for c in set(changed) if c not in known)
        if unknown:
            return _usage_error(f"unknown spec id: {', '.join(unknown)}")
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_text(report))
    return 1 if report.precondition_error is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
