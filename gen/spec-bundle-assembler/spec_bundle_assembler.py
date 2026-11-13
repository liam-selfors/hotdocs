"""Spec Bundle Assembler: builds a component's SpecBundle or CriterionBundle from the spec corpus."""

import argparse
import dataclasses
import hashlib
import importlib.util
import inspect
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Optional

__all__ = [
    "PreconditionFailure",
    "UsageError",
    "SpecBundle",
    "CriterionBundle",
    "assemble",
    "assemble_criterion",
    "main",
]


class PreconditionFailure(Exception):
    """Assembly refused: the corpus is not lint-clean or a named document is missing."""


class UsageError(ValueError):
    """The requested component id does not exist in the corpus."""


class _ReadOnlyMapping(Mapping):
    """Read-only mapping view over a dataclass's fields, in field order."""

    def __getitem__(self, key):
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}[key]

    def __iter__(self):
        return iter([f.name for f in dataclasses.fields(self)])

    def __len__(self):
        return len(dataclasses.fields(self))


@dataclasses.dataclass
class SpecBundle(_ReadOnlyMapping):
    """A component's full generation input (R-ASSEMBLE-001..014)."""

    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: Optional[dict] = None


@dataclasses.dataclass
class CriterionBundle(_ReadOnlyMapping):
    """One acceptance criterion's narrow authoring input (R-ASSEMBLE-009)."""

    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# Dependency loading (R-ASSEMBLE-015)
# ---------------------------------------------------------------------------

_TOOL_MODULES = {}

_IDENT = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z_][A-Za-z0-9_]*")
_DROPPED_SECTION = re.compile(r"^##\s+(Rationale|Open questions|Change log)\s*$")
_SECTION_HEADING = re.compile(r"^#{1,2}\s")


def _get(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _module_file(base, module_name):
    flat = base / f"{module_name}.py"
    return flat if flat.is_file() else base / module_name / "__init__.py"


def _exec_module(load_name, path):
    spec = importlib.util.spec_from_file_location(load_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


def _load_tool(slug, repo_root):
    base = repo_root / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    module_name = slug.replace("-", "_")
    path = _module_file(base, module_name).resolve()
    key = str(path)
    if key not in _TOOL_MODULES:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        _TOOL_MODULES[key] = _exec_module(f"_spec_bundle_assembler__{module_name}_{digest}", path)
    return _TOOL_MODULES[key]


def _prepare(repo_root):
    linter = _load_tool("spec-linter", repo_root)
    engine = _load_tool("graph-query-engine", repo_root)
    report = linter.lint(None, repo_root)
    failures = _get(report, "hard_failures")
    if failures:
        raise PreconditionFailure(f"corpus is not lint-clean: {failures} hard failure(s)")
    corpus = linter.load_corpus(repo_root)
    engine.load_views(_get(corpus, "graph"), repo_root)
    return corpus


# ---------------------------------------------------------------------------
# Corpus helpers
# ---------------------------------------------------------------------------


def _component_index(corpus):
    index = {}
    components = _get(corpus, "components")
    for name in sorted(components):
        comp = _get(components, name)
        fm = _get(_get(comp, "root"), "frontmatter")
        index[_get(fm, "id")] = (name, comp, fm)
    return index


def _lookup(index, component_id):
    if component_id not in index:
        raise UsageError(f"unknown component id: {component_id}")
    return index[component_id]


def _join(texts):
    return "\n\n".join(t.strip() for t in texts if t.strip())


def _interface_docs(comp):
    docs = [_get(comp, "interface_cli"), _get(comp, "interface_library")]
    for key in ("interface_data", "interface_guarantees"):
        group = _get(comp, key)
        docs.extend(_get(group, k) for k in sorted(group))
    return [d for d in docs if d is not None]


def _strip_sections(body):
    kept = []
    dropping = False
    for line in body.splitlines():
        if _SECTION_HEADING.match(line):
            dropping = bool(_DROPPED_SECTION.match(line))
        if not dropping:
            kept.append(line)
    return "\n".join(kept)


def _interface_text(repo_root, comp):
    text = _join([_get(d, "body") for d in _interface_docs(comp)])
    library_body = _get(_get(comp, "interface_library"), "body") or ""
    named = []
    for line in library_body.splitlines():
        if line.startswith("Implements:"):
            named.extend(re.findall(r"`([^`]+)`", line))
    for rel in named:
        path = repo_root / rel
        if not path.is_file():
            raise PreconditionFailure(f"Implements: names {rel}, which does not exist")
        text = f"{text}\n\n## Implements: {rel}\n\n{path.read_text(encoding='utf-8')}"
    return text, named


def _dependency_interfaces(corpus, index, fm):
    type_owners = {}
    components = _get(corpus, "components")
    for name in sorted(components):
        comp = _get(components, name)
        for stem in sorted(_get(comp, "interface_data")):
            type_owners.setdefault(stem, []).append(comp)

    result = {}
    type_paths = []
    for dep_id in _get(fm, "depends_on", []):
        _, dep, _ = index[dep_id]
        parts = [_get(d, "body") for d in _interface_docs(dep)]
        names = set(_IDENT.findall("\n".join(parts))) - set(_get(dep, "interface_data"))
        for ident in sorted(names):
            owners = type_owners.get(ident, [])
            if len(owners) == 1:
                owner = owners[0]
                doc = _get(_get(owner, "interface_data"), ident)
                owner_id = _get(_get(_get(owner, "root"), "frontmatter"), "id")
                parts.append(f"## Type: {ident} (owned by {owner_id})\n\n{_get(doc, 'body').strip()}")
                type_paths.append(_get(doc, "rel_path"))
        result[dep_id] = _join(parts)
    return result, type_paths


def _glossary(repo_root):
    return (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Filesystem / hashing helpers (R-ASSEMBLE-007)
# ---------------------------------------------------------------------------


def _md_files(repo_root, directory):
    return [p.relative_to(repo_root).as_posix() for p in directory.rglob("*.md") if p.is_file()]


def _code_files(directory):
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file()
        and not p.name.startswith(".")
        and "__pycache__" not in p.relative_to(directory).parts
    )


def _hash(mode, repo_root, rel_paths):
    digest = hashlib.sha256()
    digest.update(mode.encode("utf-8") + b"\0")
    for rel in sorted(set(rel_paths)):
        path = repo_root / rel
        if path.is_file():
            digest.update(rel.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


# ---------------------------------------------------------------------------
# Usage cards (R-ASSEMBLE-011)
# ---------------------------------------------------------------------------


def _usage_card(code_dir, rel_dir, module_name):
    path = _module_file(code_dir, module_name)
    if not path.is_file():
        return ""
    module = _exec_module(module_name, path)
    lines = [f"Importable as: `{module_name}` (module path `{rel_dir}`)."]
    namespace = module.__dict__
    for name in sorted(namespace):
        obj = namespace[name]
        if name.startswith("_"):
            continue
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        if obj.__module__ != module.__name__:
            continue
        try:
            signature = str(inspect.signature(obj))
        except (TypeError, ValueError):
            continue
        line = f"- `{name}{signature}`"
        doc_lines = (obj.__doc__ or "").strip().splitlines()
        if doc_lines:
            line += f" -- {doc_lines[0].strip()}"
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def assemble(component_id, repo_root, mode="cold"):
    """Assemble the SpecBundle for `component_id` from the corpus at `repo_root`."""
    repo_root = Path(repo_root)
    corpus = _prepare(repo_root)
    index = _component_index(corpus)
    name, comp, fm = _lookup(index, component_id)

    comp_dir = repo_root / "specs" / "components" / name
    hash_paths = [
        f"specs/components/{name}/component.md",
        f"specs/components/{name}/constraints.md",
    ]
    hash_paths += _md_files(repo_root, comp_dir / "requirements")
    hash_paths += _md_files(repo_root, comp_dir / "interface")

    requirements = _get(comp, "requirements")
    spec = _join(
        [_strip_sections(_get(_get(comp, "root"), "body"))]
        + [_get(_get(requirements, k), "body") for k in sorted(requirements)]
    )
    interface, implements = _interface_text(repo_root, comp)
    hash_paths += implements
    constraints = _join([_get(_get(comp, "constraints"), "body") or ""])

    dependency_interfaces, type_paths = _dependency_interfaces(corpus, index, fm)
    hash_paths += type_paths

    graph = _get(corpus, "graph")
    dependency_context = {}
    dependency_usage = {}
    for dep_id in _get(fm, "depends_on", []):
        dep_name, _, dep_fm = index[dep_id]
        dep_dir = repo_root / "specs" / "components" / dep_name
        hash_paths.append(f"specs/components/{dep_name}/component.md")
        hash_paths += _md_files(repo_root, dep_dir / "interface")
        row = graph.execute(
            "SELECT purpose FROM component_context WHERE component_id = ?", [dep_id]
        ).fetchone()
        dependency_context[dep_id] = row[0].strip()
        if _get(dep_fm, "sealed"):
            rel_dir = _get(dep_fm, "source_path").rstrip("/") + "/"
        else:
            rel_dir = f"gen/{dep_name}/"
        code_dir = repo_root / rel_dir
        hash_paths += [p.relative_to(repo_root).as_posix() for p in _code_files(code_dir)]
        dependency_usage[dep_id] = _usage_card(code_dir, rel_dir, dep_name.replace("-", "_"))

    id_index = _get(corpus, "id_index")
    var_texts = {}
    for var_id in _get(fm, "uses_var", []):
        doc = _get(id_index, var_id)
        var_texts[var_id] = Path(_get(doc, "path")).read_text(encoding="utf-8")
        hash_paths.append(_get(doc, "rel_path"))

    hash_paths.append("specs/glossary.md")
    glossary = _glossary(repo_root)

    hint_code = None
    if mode == "hint":
        gen_dir = repo_root / "gen" / name
        files = _code_files(gen_dir)
        hint_code = {
            p.relative_to(gen_dir).as_posix(): p.read_text(encoding="utf-8", errors="replace")
            for p in files
        }
        hash_paths += [p.relative_to(repo_root).as_posix() for p in files]

    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=_hash(mode, repo_root, hash_paths),
        spec=spec,
        interface=interface,
        constraints=constraints,
        dependency_interfaces=dependency_interfaces,
        dependency_context=dependency_context,
        dependency_usage=dependency_usage,
        vars=var_texts,
        glossary=glossary,
        hint_code=hint_code,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    """Assemble the CriterionBundle for one acceptance criterion of `component_id`."""
    repo_root = Path(repo_root)
    corpus = _prepare(repo_root)
    index = _component_index(corpus)
    _, comp, fm = _lookup(index, component_id)

    criterion = _get(_get(comp, "acceptance"), criterion_id)
    rows = _get(corpus, "graph").execute(
        "SELECT target_id FROM edges WHERE source_id = ? AND edge_type = 'covers' ORDER BY target_id",
        [criterion_id],
    ).fetchall()
    covered = [row[0] for row in rows]
    requirements = _get(comp, "requirements")
    interface, _ = _interface_text(repo_root, comp)
    dependency_interfaces, _ = _dependency_interfaces(corpus, index, fm)

    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=", ".join(covered),
        criterion_text=_join([_get(criterion, "body")]),
        requirement_text=_join([_get(_get(requirements, r), "body") for r in covered]),
        interface=interface,
        glossary=_glossary(repo_root),
        dependency_interfaces=dependency_interfaces,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _summary(bundle):
    return "\n".join(
        [
            f"component: {bundle.component_id}",
            f"spec_bundle_hash: {bundle.spec_bundle_hash}",
            f"dependencies: {', '.join(bundle.dependency_interfaces)}",
            f"vars: {', '.join(bundle.vars)}",
        ]
    )


def main(argv=None):
    """Run `hotdocs assemble`; returns the exit code (0 ok, 1 precondition failure, 2 usage error)."""
    parser = argparse.ArgumentParser(prog="hotdocs assemble")
    parser.add_argument("component_id")
    parser.add_argument("--mode", choices=["cold", "hint"], default="cold")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)
    try:
        bundle = assemble(args.component_id, Path(args.repo_root), args.mode)
    except PreconditionFailure as exc:
        print(f"precondition failure: {exc}", file=sys.stderr)
        return 1
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(dataclasses.asdict(bundle), indent=2))
    else:
        print(_summary(bundle))
    return 0


if __name__ == "__main__":
    sys.exit(main())