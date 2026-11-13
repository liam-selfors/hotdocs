"""Impact analyzer: computes the minimal blast radius for a set of changed spec ids.

Library: ``compute_blast_radius(changed_ids, repo_root) -> BlastRadiusReport``.
CLI: ``main(argv)`` receives the tokens after ``hotdocs impact`` and returns
the exit code (0 computed, 1 precondition failure, 2 usage error).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

REASON_RANK = {
    "direct": 0,
    "transitive-interface": 1,
    "transitive-var": 2,
    "transitive-capability": 3,
    "transitive-guarantee": 4,
}


@dataclass
class ImpactedComponent:
    component_id: str
    reason: str
    via: Optional[str] = None
    guarantee_ids: Optional[List[str]] = None

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self) -> dict:
        data = {
            "component_id": self.component_id,
            "reason": self.reason,
            "via": self.via,
        }
        if self.reason == "transitive-guarantee":
            data["guarantee_ids"] = list(self.guarantee_ids)
        return data


@dataclass
class BlastRadiusReport:
    impacted: List[ImpactedComponent] = field(default_factory=list)
    precondition_error: Optional[str] = None

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self) -> dict:
        return {
            "impacted": [entry.to_dict() for entry in self.impacted],
            "precondition_error": self.precondition_error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Dependency loading (spec-linter)
# ---------------------------------------------------------------------------


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve().parent
    for directory in [here, *here.parents]:
        if directory.name == "gen":
            return directory.parent
    return here


def _load_spec_linter(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / "spec-linter"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "spec-linter"
    flat = dep_dir / "spec_linter.py"
    package_init = dep_dir / "spec_linter" / "__init__.py"
    target = flat if flat.is_file() else package_init
    digest = hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:16]
    name = f"_impact_analyzer_dep_spec_linter_{digest}"
    if target == flat:
        spec = importlib.util.spec_from_file_location(name, flat)
    else:
        spec = importlib.util.spec_from_file_location(
            name, package_init, submodule_search_locations=[str(package_init.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Git comparison against the merge-base with the default branch
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> Optional[bytes]:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True)
    return result.stdout if result.returncode == 0 else None


def _merge_base(repo_root: Path) -> Optional[str]:
    origin_head = _git(repo_root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    candidates = [origin_head.decode().strip()] if origin_head else []
    candidates += ["main", "master"]
    for ref in candidates:
        out = _git(repo_root, "merge-base", "HEAD", ref)
        if out:
            return out.decode().strip()
    return None


def _list_files(repo_root: Path, base: Optional[str], rel_dir: str) -> List[str]:
    names = set()
    if base:
        out = _git(repo_root, "ls-tree", "-r", "-z", "--name-only", base, "--", rel_dir + "/")
        names.update(n for n in (out or b"").decode().split("\0") if n)
    names.update(
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / rel_dir).rglob("*")
        if p.is_file()
    )
    return sorted(names)


def _at_base(repo_root: Path, base: Optional[str], rel: str) -> Optional[bytes]:
    return _git(repo_root, "show", f"{base}:./{rel}") if base else None


def _in_tree(repo_root: Path, rel: str) -> Optional[bytes]:
    path = repo_root / rel
    return path.read_bytes() if path.is_file() else None


def _changed_files(repo_root: Path, base: Optional[str], rels: List[str]) -> List[str]:
    return [r for r in rels if _at_base(repo_root, base, r) != _in_tree(repo_root, r)]


# ---------------------------------------------------------------------------
# Blast radius computation
# ---------------------------------------------------------------------------


def _as_list(value) -> List[str]:
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return [value] if value else []


def _precondition_message(lint_report, failures) -> str:
    details = [
        f"{_get(f, 'file')}:{_get(f, 'line')}: {_get(f, 'rule_id')}: {_get(f, 'message')}"
        for f in (_get(lint_report, "findings") or [])
        if _get(f, "severity") == "fail"
    ]
    message = f"corpus is not lint-clean ({failures} fail-severity finding(s))"
    return message + "".join("\n  " + d for d in details)


def compute_blast_radius(changed_ids: List[str], repo_root: Path) -> BlastRadiusReport:
    repo_root = Path(repo_root)
    linter = _load_spec_linter(repo_root)
    lint_report = linter.lint(None, repo_root)
    failures = _get(lint_report, "hard_failures", 0)
    if failures:
        return BlastRadiusReport(
            impacted=[], precondition_error=_precondition_message(lint_report, failures)
        )

    corpus = linter.load_corpus(repo_root)
    id_index = _get(corpus, "id_index") or {}
    unknown = sorted({c for c in changed_ids if c not in id_index})
    if unknown:
        raise ValueError("unknown spec id(s): " + ", ".join(unknown))

    comps = {}
    for slug, comp in sorted((_get(corpus, "components") or {}).items()):
        root = _get(comp, "root")
        comps[_get(root, "doc_id")] = (
            slug,
            _get(root, "frontmatter") or {},
            set(_get(comp, "interface_guarantees") or {}),
        )

    dependents, var_users, realizers = {}, {}, {}
    for comp_id, (_, frontmatter, _) in comps.items():
        for upstream in _as_list(_get(frontmatter, "depends_on")):
            dependents.setdefault(upstream, []).append(comp_id)
        for var_id in _as_list(_get(frontmatter, "uses_var")):
            var_users.setdefault(var_id, []).append(comp_id)
        for cap_id in _as_list(_get(frontmatter, "realizes")):
            realizers.setdefault(cap_id, []).append(comp_id)

    base = _merge_base(repo_root)
    changed = sorted(set(changed_ids))
    offers = []
    for cid in changed:
        if cid in comps:
            slug, _, up_guarantees = comps[cid]
            iface = f"specs/components/{slug}/interface"
            surface = [f"{iface}/cli.md", f"{iface}/library.md"] + _list_files(
                repo_root, base, f"{iface}/data"
            )
            if _changed_files(repo_root, base, surface):
                for dep in dependents.get(cid, []):
                    offers.append(("transitive-interface", cid, dep, None))
            guarantee_files = _list_files(repo_root, base, f"{iface}/guarantees")
            g_changed = {Path(p).stem for p in _changed_files(repo_root, base, guarantee_files)}
            if g_changed:
                known = up_guarantees | g_changed
                for dep in dependents.get(cid, []):
                    declared = _as_list(_get(comps[dep][1], "depends_on_guarantees"))
                    owned = {g for g in declared if g in known}
                    hit = sorted(owned & g_changed) if owned else sorted(g_changed)
                    if hit:
                        offers.append(("transitive-guarantee", cid, dep, hit))
        for dep in var_users.get(cid, []):
            offers.append(("transitive-var", cid, dep, None))
        for dep in realizers.get(cid, []):
            offers.append(("transitive-capability", cid, dep, None))

    chosen = {cid: ImpactedComponent(cid, "direct") for cid in changed if cid in comps}
    for reason, via, dep, gids in sorted(offers, key=lambda o: (REASON_RANK[o[0]], o[1], o[2])):
        if dep not in chosen:
            chosen[dep] = ImpactedComponent(dep, reason, via, gids)
    impacted = sorted(chosen.values(), key=lambda e: (REASON_RANK[e.reason], e.component_id))
    return BlastRadiusReport(impacted=impacted, precondition_error=None)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_repo_root() -> Path:
    out = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(out.decode().strip()) if out else Path.cwd()


def _format_text(report: BlastRadiusReport) -> str:
    if report.precondition_error is not None:
        return f"precondition error: {report.precondition_error}"
    lines = []
    for entry in report.impacted:
        line = f"{entry.component_id}\t{entry.reason}"
        if entry.via is not None:
            line += f"\tvia {entry.via}"
        if entry.guarantee_ids is not None:
            line += "\t" + ", ".join(entry.guarantee_ids)
        lines.append(line)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs impact")
    parser.add_argument("--changed", nargs="+", action="extend", required=True)
    parser.add_argument("--repo-root")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code

    repo_root = Path(args.repo_root) if args.repo_root else _default_repo_root()
    try:
        report = compute_blast_radius(args.changed, repo_root)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(report.to_json())
    else:
        print(_format_text(report))
    return 1 if report.precondition_error is not None else 0