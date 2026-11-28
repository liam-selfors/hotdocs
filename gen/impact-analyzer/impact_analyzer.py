"""Impact analyzer: computes the blast radius of a set of changed spec ids."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = "usage: hotdocs impact --changed <spec-id>... [--repo-root=<dir>] [--format=json|text]"

_TYPE_FILES = ("cli.md", "library.md")


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


@dataclass
class ImpactedComponent:
    component_id: str
    reason: str
    via: object = None
    guarantee_ids: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        out = {"component_id": self.component_id, "reason": self.reason, "via": self.via}
        if self.guarantee_ids is not None:
            out["guarantee_ids"] = list(self.guarantee_ids)
        return out


@dataclass
class BlastRadiusReport:
    impacted: list = field(default_factory=list)
    precondition_error: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        return {
            "impacted": [entry.to_dict() for entry in self.impacted],
            "precondition_error": self.precondition_error,
        }


# --- dependency loading -------------------------------------------------------


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_spec_linter(repo_root: Path):
    base = Path(repo_root) / "gen" / "spec-linter"
    if not base.is_dir():
        base = _tool_root() / "gen" / "spec-linter"
    pkg_init = base / "spec_linter" / "__init__.py"
    if pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            "spec_linter", pkg_init, submodule_search_locations=[str(pkg_init.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location("spec_linter", base / "spec_linter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


# --- git / change detection ---------------------------------------------------


def _git(repo_root: Path, *args):
    proc = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True)
    if proc.returncode != 0:
        return None
    return proc.stdout


def _prior_commit(repo_root: Path):
    branch = None
    ref = _git(repo_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if ref is not None:
        branch = ref.decode().strip()
    else:
        for candidate in ("refs/heads/main", "refs/heads/master"):
            if _git(repo_root, "rev-parse", "--verify", "--quiet", candidate) is not None:
                branch = candidate
                break
    if branch is None:
        return None
    base = _git(repo_root, "merge-base", "HEAD", branch)
    if base is None:
        return None
    return base.decode().strip()


def _prior_files(repo_root: Path, commit, rel_dir: str):
    if commit is None:
        return {}
    listing = _git(repo_root, "ls-tree", "-r", "--name-only", "-z", commit, "--", "./" + rel_dir + "/")
    if listing is None:
        return {}
    files = {}
    prefix = rel_dir + "/"
    for raw in listing.decode().split("\0"):
        if not raw.startswith(prefix):
            continue
        content = _git(repo_root, "cat-file", "blob", commit + ":./" + raw)
        files[raw[len(prefix):]] = content
    return files


def _current_files(repo_root: Path, rel_dir: str):
    base = Path(repo_root) / rel_dir
    return {
        p.relative_to(base).as_posix(): p.read_bytes()
        for p in sorted(base.rglob("*"))
        if p.is_file()
    }


def _guarantee_id(rel: str):
    if not rel.startswith("guarantees/"):
        return None
    name = rel[len("guarantees/"):]
    if "/" in name or not name.startswith("G-") or not name.endswith(".md"):
        return None
    return name[: -len(".md")]


def _interface_changes(repo_root: Path, commit, slug: str):
    rel_dir = "specs/components/" + slug + "/interface"
    prior = _prior_files(repo_root, commit, rel_dir)
    current = _current_files(repo_root, rel_dir)
    type_changed = False
    changed_guarantees = set()
    for rel in sorted(set(prior) | set(current)):
        if prior.get(rel) == current.get(rel):
            continue
        if rel in _TYPE_FILES or rel.startswith("data/"):
            type_changed = True
        gid = _guarantee_id(rel)
        if gid is not None:
            changed_guarantees.add(gid)
    owned = {g for g in (_guarantee_id(rel) for rel in current) if g is not None}
    return type_changed, changed_guarantees, owned


# --- core ---------------------------------------------------------------------


def _frontmatter(component):
    root = _get(component, "root")
    if root is None:
        return {}
    return _get(root, "frontmatter") or {}


def _lint_failures(linter, repo_root: Path):
    report = linter.lint(None, repo_root)
    return sum(1 for f in (_get(report, "findings") or []) if _get(f, "severity") == "fail")


def compute_blast_radius(changed_ids, repo_root) -> BlastRadiusReport:
    repo_root = Path(repo_root)
    linter = _load_spec_linter(repo_root)
    failures = _lint_failures(linter, repo_root)
    if failures:
        return BlastRadiusReport(
            impacted=[],
            precondition_error=(
                f"corpus did not pass spec-linter cleanly ({failures} fail-severity finding(s))"
            ),
        )
    corpus = linter.load_corpus(repo_root)
    components = _get(corpus, "components") or {}
    slugs = sorted(components)
    fms = {"comp-" + slug: _frontmatter(components[slug]) for slug in slugs}

    doc_types = {}
    for doc in _get(corpus, "docs") or []:
        doc_types[_get(doc, "doc_id")] = _get(doc, "doc_type")

    changed = sorted(set(changed_ids))
    changed_components = [c for c in changed if c in fms]
    changed_vars = [c for c in changed if doc_types.get(c) == "var"]
    changed_caps = [c for c in changed if doc_types.get(c) == "product"]

    direct = {cid: ImpactedComponent(cid, "direct", None) for cid in changed_components}
    found = {}

    def add(cid, entry):
        if cid not in direct and cid not in found:
            found[cid] = entry

    commit = _prior_commit(repo_root) if changed_components else None

    for upstream in changed_components:
        slug = upstream[len("comp-"):]
        type_changed, changed_g, owned = _interface_changes(repo_root, commit, slug)
        dependents = [
            cid for cid in sorted(fms)
            if cid != upstream and upstream in (fms[cid].get("depends_on") or [])
        ]
        if type_changed:
            for cid in dependents:
                add(cid, ImpactedComponent(cid, "transitive-interface", upstream))
        if changed_g:
            for cid in dependents:
                declared = set(fms[cid].get("depends_on_guarantees") or []) & owned
                if declared:
                    hit = declared & changed_g
                    if hit:
                        add(cid, ImpactedComponent(cid, "transitive-guarantee", upstream, sorted(hit)))
                else:
                    add(cid, ImpactedComponent(cid, "transitive-guarantee", upstream, sorted(changed_g)))

    for var in changed_vars:
        for cid in sorted(fms):
            if var in (fms[cid].get("uses_var") or []):
                add(cid, ImpactedComponent(cid, "transitive-var", var))

    for cap in changed_caps:
        for cid in sorted(fms):
            if cap in (fms[cid].get("realizes") or []):
                add(cid, ImpactedComponent(cid, "transitive-capability", cap))

    impacted = [direct[c] for c in sorted(direct)] + [found[c] for c in sorted(found)]
    return BlastRadiusReport(impacted=impacted, precondition_error=None)


# --- CLI ----------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse(argv):
    ids = []
    repo_root = None
    fmt = "text"
    collecting = False
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--changed":
            collecting = True
        elif tok.startswith("--changed="):
            ids.append(tok[len("--changed="):])
            collecting = True
        elif tok in ("--repo-root", "--format"):
            collecting = False
            if i + 1 >= len(argv):
                raise _UsageError(f"{tok} requires a value")
            i += 1
            if tok == "--repo-root":
                repo_root = argv[i]
            else:
                fmt = argv[i]
        elif tok.startswith("--repo-root="):
            collecting = False
            repo_root = tok[len("--repo-root="):]
        elif tok.startswith("--format="):
            collecting = False
            fmt = tok[len("--format="):]
        elif tok.startswith("-"):
            raise _UsageError(f"unknown argument: {tok}")
        elif collecting:
            ids.append(tok)
        else:
            raise _UsageError(f"unknown argument: {tok}")
        i += 1
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format value: {fmt}")
    if not ids:
        raise _UsageError("--changed requires at least one spec id")
    return ids, repo_root, fmt


def _default_repo_root():
    out = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if out is None:
        return Path.cwd()
    return Path(out.decode().strip())


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _known_ids(repo_root: Path):
    corpus = _load_spec_linter(repo_root).load_corpus(repo_root)
    known = {_get(doc, "doc_id") for doc in (_get(corpus, "docs") or [])}
    known |= set(_get(corpus, "id_index") or {})
    known |= {"comp-" + slug for slug in (_get(corpus, "components") or {})}
    return known


def _render_text(report: BlastRadiusReport):
    if report.precondition_error is not None:
        return f"precondition error: {report.precondition_error}"
    if not report.impacted:
        return "no components impacted"
    lines = []
    for entry in report.impacted:
        parts = [entry.component_id, entry.reason]
        if entry.via is not None:
            parts.append(f"via {entry.via}")
        if entry.reason == "transitive-guarantee":
            parts.append(",".join(entry.guarantee_ids))
        lines.append("\t".join(parts))
    return "\n".join(lines)


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        ids, repo_root, fmt = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(str(exc))
    root = Path(repo_root) if repo_root is not None else _default_repo_root()
    known = _known_ids(root)
    for spec_id in ids:
        if spec_id not in known:
            return _usage_error(f"unknown spec id: {spec_id}")
    report = compute_blast_radius(ids, root)
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_render_text(report))
    return 1 if report.precondition_error is not None else 0


if __name__ == "__main__":
    sys.exit(main())
