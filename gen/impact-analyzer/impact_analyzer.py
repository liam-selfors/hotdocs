"""Impact analyzer: computes the blast radius of a set of changed spec ids."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = (
    "usage: hotdocs impact --changed <spec-id>... "
    "[--repo-root=<dir>] [--format=json|text]"
)

_LOADED: dict = {}


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


@dataclass
class ImpactedComponent:
    component_id: str
    reason: str
    via: str | None = None
    guarantee_ids: list | None = None

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        out = {
            "component_id": self.component_id,
            "reason": self.reason,
            "via": self.via,
        }
        if self.reason == "transitive-guarantee":
            out["guarantee_ids"] = list(self.guarantee_ids)
        return out


@dataclass
class BlastRadiusReport:
    impacted: list = field(default_factory=list)
    precondition_error: str | None = None

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        return {
            "impacted": [entry.to_dict() for entry in self.impacted],
            "precondition_error": self.precondition_error,
        }


# --------------------------------------------------------------------------
# Dependency loading
# --------------------------------------------------------------------------

def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load_spec_linter(repo_root: Path):
    dep = Path(repo_root) / "gen" / "spec-linter"
    if not dep.is_dir():
        dep = _tool_root() / "gen" / "spec-linter"
    pkg_init = dep / "spec_linter" / "__init__.py"
    if pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            "spec_linter", pkg_init, submodule_search_locations=[str(pkg_init.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location("spec_linter", dep / "spec_linter.py")
    key = str(Path(spec.origin).resolve())
    if key in _LOADED:
        sys.modules["spec_linter"] = _LOADED[key]
        return _LOADED[key]
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    _LOADED[key] = module
    return module


# --------------------------------------------------------------------------
# Git / prior-commit change detection (R-IMPACT-010)
# --------------------------------------------------------------------------

def _git(repo_root: Path, *args):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args], capture_output=True
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _prior_commit(repo_root: Path):
    target = _git(repo_root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    if target is not None:
        branch = target.decode().strip()
    else:
        branch = next(
            (
                ref
                for ref in ("refs/heads/main", "refs/heads/master")
                if _git(repo_root, "rev-parse", "--verify", "-q", ref) is not None
            ),
            None,
        )
    if branch is None:
        return None
    base = _git(repo_root, "merge-base", "HEAD", branch)
    if base is None:
        return None
    prefix = _git(repo_root, "rev-parse", "--show-prefix")
    return base.decode().strip(), (prefix or b"").decode().strip()


def _prior_listing(repo_root: Path, prior, rel_dir: str):
    if prior is None:
        return []
    out = _git(repo_root, "ls-tree", "-r", "-z", "--name-only", prior[0], "--", rel_dir)
    return [p for p in (out or b"").decode().split("\0") if p]


def _file_changed(repo_root: Path, prior, rel: str) -> bool:
    path = repo_root / rel
    current = path.read_bytes() if path.is_file() else None
    old = None
    if prior is not None:
        old = _git(repo_root, "cat-file", "blob", f"{prior[0]}:{prior[1]}{rel}")
    return old != current


def _contract_changed(repo_root: Path, prior, slug: str) -> bool:
    base = f"specs/components/{slug}/interface"
    data = f"{base}/data"
    paths = {f"{base}/cli.md", f"{base}/library.md"}
    paths |= {
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / data).rglob("*")
        if p.is_file()
    }
    paths |= set(_prior_listing(repo_root, prior, data))
    return any(_file_changed(repo_root, prior, p) for p in sorted(paths))


def _is_guarantee_name(name: str) -> bool:
    return "/" not in name and name.startswith("G-") and name.endswith(".md")


def _changed_guarantees(repo_root: Path, prior, slug: str) -> set:
    gdir = f"specs/components/{slug}/interface/guarantees"
    names = {p.name for p in (repo_root / gdir).glob("G-*.md") if p.is_file()}
    names |= {p[len(gdir) + 1:] for p in _prior_listing(repo_root, prior, gdir)}
    return {
        Path(name).stem
        for name in sorted(names)
        if _is_guarantee_name(name) and _file_changed(repo_root, prior, f"{gdir}/{name}")
    }


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

def _analyze(changed_ids, repo_root):
    repo_root = Path(repo_root)
    linter = _load_spec_linter(repo_root)
    corpus = linter.load_corpus(repo_root)
    components = _get(corpus, "components") or {}
    docs = _get(corpus, "docs") or []
    id_index = _get(corpus, "id_index") or {}

    known = {_get(doc, "doc_id") for doc in docs}
    unknown = sorted(i for i in set(changed_ids) if i not in known)

    lint_report = linter.lint(None, repo_root)
    fails = sum(
        1 for f in (_get(lint_report, "findings") or []) if _get(f, "severity") == "fail"
    )
    if fails:
        return (
            BlastRadiusReport(
                [], f"corpus is not lint-clean: {fails} fail-severity finding(s)"
            ),
            unknown,
        )

    slug_of: dict = {}
    fm_of: dict = {}
    guarantees_of: dict = {}
    holds: dict = {}
    for slug in sorted(components):
        comp = components[slug]
        root = _get(comp, "root")
        if root is None:
            continue
        cid = _get(root, "doc_id")
        slug_of[cid] = slug
        fm_of[cid] = _get(root, "frontmatter") or {}
        guarantees_of[cid] = set(_get(comp, "interface_guarantees") or {})
        for unit_id in list(_get(comp, "requirements") or {}) + list(
            _get(comp, "acceptance") or {}
        ):
            holds.setdefault(unit_id, cid)

    unique = sorted(set(changed_ids))
    direct = set()
    for spec_id in unique:
        if spec_id in slug_of:
            direct.add(spec_id)
        elif spec_id in holds:
            direct.add(holds[spec_id])
    changed_vars = [i for i in unique if _get(id_index.get(i), "doc_type") == "var"]
    changed_caps = [i for i in unique if _get(id_index.get(i), "doc_type") == "product"]

    def referrers(key, target):
        return [c for c in sorted(fm_of) if target in _list(_get(fm_of[c], key))]

    found: dict = {}

    def add(entry):
        if entry.component_id not in direct and entry.component_id not in found:
            found[entry.component_id] = entry

    prior = _prior_commit(repo_root)
    for upstream in sorted(direct):
        slug = slug_of[upstream]
        dependents = referrers("depends_on", upstream)
        if _contract_changed(repo_root, prior, slug):
            for dep in dependents:
                add(ImpactedComponent(dep, "transitive-interface", upstream))
        changed_g = _changed_guarantees(repo_root, prior, slug)
        if changed_g:
            owned = guarantees_of[upstream] | changed_g
            for dep in dependents:
                declared = {
                    g for g in _list(_get(fm_of[dep], "depends_on_guarantees")) if g in owned
                }
                hit = sorted(declared & changed_g) if declared else sorted(changed_g)
                if hit:
                    add(ImpactedComponent(dep, "transitive-guarantee", upstream, hit))

    for var_id in changed_vars:
        for dep in referrers("uses_var", var_id):
            add(ImpactedComponent(dep, "transitive-var", var_id))

    for cap_id in changed_caps:
        for dep in referrers("realizes", cap_id):
            add(ImpactedComponent(dep, "transitive-capability", cap_id))

    impacted = [ImpactedComponent(c, "direct", None) for c in sorted(direct)]
    impacted += [found[c] for c in sorted(found)]
    return BlastRadiusReport(impacted, None), unknown


def compute_blast_radius(changed_ids: list[str], repo_root: Path) -> BlastRadiusReport:
    return _analyze(changed_ids, repo_root)[0]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _usage(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _default_root() -> Path:
    out = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(out.decode().strip()) if out else Path.cwd()


def _text(report: BlastRadiusReport) -> str:
    if report.precondition_error is not None:
        return f"precondition error: {report.precondition_error}"
    if not report.impacted:
        return "no components impacted"
    lines = []
    for entry in report.impacted:
        line = f"{entry.component_id}\t{entry.reason}"
        if entry.via is not None:
            line += f"\tvia {entry.via}"
        if entry.reason == "transitive-guarantee":
            line += "\t" + ",".join(entry.guarantee_ids)
        lines.append(line)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    changed: list = []
    repo_root = None
    fmt = "text"
    in_changed = False
    i = 0
    while i < len(args):
        tok = args[i]
        i += 1
        if tok == "--changed":
            in_changed = True
            continue
        if tok.startswith("--changed="):
            changed.append(tok[len("--changed="):])
            in_changed = True
            continue
        if not tok.startswith("-"):
            if in_changed:
                changed.append(tok)
                continue
            return _usage(f"unknown argument: {tok}")
        in_changed = False
        name, eq, value = tok.partition("=")
        if name not in ("--repo-root", "--format"):
            return _usage(f"unknown argument: {tok}")
        if not eq:
            if i >= len(args):
                return _usage(f"{name} requires a value")
            value = args[i]
            i += 1
        if name == "--repo-root":
            repo_root = value
        else:
            if value not in ("json", "text"):
                return _usage(f"invalid --format value: {value}")
            fmt = value
    if not changed:
        return _usage("--changed requires at least one spec id")

    root = Path(repo_root) if repo_root is not None else _default_root()
    report, unknown = _analyze(changed, root)
    if unknown:
        return _usage(f"unknown spec id: {unknown[0]}")
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_text(report))
    return 1 if report.precondition_error is not None else 0


if __name__ == "__main__":
    sys.exit(main())
