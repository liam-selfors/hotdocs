"""impact-analyzer: computes the blast radius of a set of changed spec ids."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

USAGE = "usage: hotdocs impact --changed <spec-id>... [--repo-root=<dir>] [--format=json|text]"

_LOADED: dict = {}


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


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
# dependency loading


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_spec_linter(repo_root: Path):
    base = Path(repo_root) / "gen" / "spec-linter"
    if not base.is_dir():
        base = _tool_root() / "gen" / "spec-linter"
    pkg = base / "spec_linter" / "__init__.py"
    if pkg.is_file():
        target = pkg
        spec = importlib.util.spec_from_file_location(
            "spec_linter", pkg, submodule_search_locations=[str(pkg.parent)]
        )
    else:
        target = base / "spec_linter.py"
        spec = importlib.util.spec_from_file_location("spec_linter", target)
    key = str(target.resolve())
    if key in _LOADED:
        sys.modules["spec_linter"] = _LOADED[key]
        return _LOADED[key]
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    _LOADED[key] = module
    return module


# --------------------------------------------------------------------------
# git comparison (R-IMPACT-010)


def _git(repo_root: Path, *args):
    r = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True)
    return r.returncode, r.stdout


def _prior_commit(repo_root: Path):
    rc, out = _git(repo_root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    branch = out.decode().strip() if rc == 0 else None
    if branch is None:
        for name in ("main", "master"):
            rc, _ = _git(repo_root, "rev-parse", "--verify", "-q", f"refs/heads/{name}")
            if rc == 0:
                branch = f"refs/heads/{name}"
                break
    if branch is None:
        return None
    rc, out = _git(repo_root, "merge-base", "HEAD", branch)
    if rc != 0:
        return None
    return out.decode().strip()


def _base_files(repo_root: Path, base, prefix: str) -> set:
    if base is None:
        return set()
    rc, out = _git(repo_root, "ls-tree", "-r", "-z", "--name-only", base, "--", "./" + prefix)
    if rc != 0:
        return set()
    return {n.decode() for n in out.split(b"\0") if n}


def _work_files(repo_root: Path, prefix: str) -> set:
    d = Path(repo_root) / prefix
    if not d.is_dir():
        return set()
    return {
        p.relative_to(repo_root).as_posix() for p in d.rglob("*") if p.is_file()
    }


def _file_changed(repo_root: Path, base, base_files: set, rel: str) -> bool:
    path = Path(repo_root) / rel
    in_work = path.is_file()
    in_base = rel in base_files
    if in_work != in_base:
        return True
    _, old = _git(repo_root, "cat-file", "blob", f"{base}:./{rel}")
    return old != path.read_bytes()


def _interface_changes(repo_root: Path, base, slug: str):
    prefix = f"specs/components/{slug}/interface/"
    base_files = _base_files(repo_root, base, prefix)
    all_files = sorted(base_files | _work_files(repo_root, prefix))
    iface = False
    guarantees = set()
    for rel in all_files:
        p = PurePosixPath(rel)
        is_iface = rel in (prefix + "cli.md", prefix + "library.md") or rel.startswith(
            prefix + "data/"
        )
        is_guarantee = (
            str(p.parent) == prefix + "guarantees"
            and p.name.startswith("G-")
            and p.suffix == ".md"
        )
        if not (is_iface or is_guarantee):
            continue
        if not _file_changed(repo_root, base, base_files, rel):
            continue
        if is_iface:
            iface = True
        else:
            guarantees.add(p.stem)
    return iface, guarantees


# --------------------------------------------------------------------------
# library


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def compute_blast_radius(changed_ids: list, repo_root: Path) -> BlastRadiusReport:
    repo_root = Path(repo_root)
    linter = _load_spec_linter(repo_root)
    lint_report = linter.lint(None, repo_root)
    failures = _get(lint_report, "hard_failures", 0)
    if failures:
        return BlastRadiusReport(
            impacted=[],
            precondition_error=(
                f"corpus did not pass spec-linter cleanly: {failures} fail-severity finding(s)"
            ),
        )

    corpus = linter.load_corpus(repo_root)
    components = _get(corpus, "components", {}) or {}

    comp_slug: dict = {}
    comp_fm: dict = {}
    guarantee_owner: dict = {}
    for slug in sorted(components):
        comp = components[slug]
        root = _get(comp, "root")
        if root is None:
            continue
        cid = _get(root, "doc_id")
        comp_slug[cid] = slug
        comp_fm[cid] = _get(root, "frontmatter", {}) or {}
        for gid in sorted(_get(comp, "interface_guarantees", {}) or {}):
            guarantee_owner[gid] = cid

    var_ids = set()
    product_ids = set()
    for doc in _get(corpus, "docs", []) or []:
        doc_type = _get(doc, "doc_type")
        if doc_type == "var":
            var_ids.add(_get(doc, "doc_id"))
        elif doc_type == "product":
            product_ids.add(_get(doc, "doc_id"))

    changed = set(changed_ids)
    changed_comps = sorted(changed & set(comp_slug))
    changed_vars = sorted(changed & var_ids)
    changed_caps = sorted(changed & product_ids)

    def referencing(field_name: str, target: str) -> list:
        return sorted(
            cid for cid, fm in comp_fm.items() if target in _as_list(_get(fm, field_name))
        )

    direct = {cid: ImpactedComponent(cid, "direct") for cid in changed_comps}
    rest: dict = {}

    def add(entry: ImpactedComponent):
        if entry.component_id in direct or entry.component_id in rest:
            return
        rest[entry.component_id] = entry

    base = _prior_commit(repo_root) if changed_comps else None
    for upstream in changed_comps:
        iface, g_changed = _interface_changes(repo_root, base, comp_slug[upstream])
        dependents = referencing("depends_on", upstream)
        if iface:
            for dep in dependents:
                add(ImpactedComponent(dep, "transitive-interface", upstream))
        if g_changed:
            for dep in dependents:
                declared = {
                    g
                    for g in _as_list(_get(comp_fm[dep], "depends_on_guarantees"))
                    if guarantee_owner.get(g) == upstream
                }
                hit = (declared & g_changed) if declared else g_changed
                if hit:
                    add(
                        ImpactedComponent(
                            dep, "transitive-guarantee", upstream, sorted(hit)
                        )
                    )
    for var in changed_vars:
        for dep in referencing("uses_var", var):
            add(ImpactedComponent(dep, "transitive-var", var))
    for cap in changed_caps:
        for dep in referencing("realizes", cap):
            add(ImpactedComponent(dep, "transitive-capability", cap))

    impacted = [direct[k] for k in sorted(direct)] + [rest[k] for k in sorted(rest)]
    return BlastRadiusReport(impacted=impacted, precondition_error=None)


# --------------------------------------------------------------------------
# CLI


class _UsageError(Exception):
    pass


def _parse(argv: list):
    changed: list = []
    repo_root = None
    fmt = "text"
    i = 0
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok == "--changed" or tok.startswith("--changed="):
            if tok == "--changed":
                if i == n - 1:
                    raise _UsageError("--changed requires a value")
            else:
                changed.append(tok[len("--changed="):])
            i += 1
            while i < n and not argv[i].startswith("-"):
                changed.append(argv[i])
                i += 1
            continue
        if tok in ("--repo-root", "--format"):
            if i == n - 1:
                raise _UsageError(f"{tok} requires a value")
            name, value = tok, argv[i + 1]
            i += 2
        elif tok.startswith("--repo-root=") or tok.startswith("--format="):
            name, value = tok.split("=", 1)
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
        raise _UsageError("--changed requires at least one spec id")
    return changed, repo_root, fmt


def _default_repo_root() -> Path:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return Path(r.stdout.strip() or ".")


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        changed, repo_root, fmt = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(str(exc))
    root = Path(repo_root) if repo_root is not None else _default_repo_root()

    corpus = _load_spec_linter(root).load_corpus(root)
    known = _get(corpus, "id_index", {}) or {}
    for cid in changed:
        if cid not in known:
            return _usage_error(f"unknown spec id: {cid}")

    report = compute_blast_radius(changed, root)
    error = _get(report, "precondition_error")
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
    elif error is not None:
        print(f"precondition error: {error}")
    elif not report.impacted:
        print("no components impacted")
    else:
        for entry in report.impacted:
            parts = [entry.component_id, entry.reason]
            if entry.via is not None:
                parts.append(f"via {entry.via}")
            if entry.reason == "transitive-guarantee":
                parts.append(",".join(entry.guarantee_ids))
            print("\t".join(parts))
    return 1 if error is not None else 0


if __name__ == "__main__":
    sys.exit(main())
