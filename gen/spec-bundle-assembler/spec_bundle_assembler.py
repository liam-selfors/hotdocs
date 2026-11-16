"""Spec bundle assembler: builds a component's ``SpecBundle`` or ``CriterionBundle``.

One assembly implementation, shared by canonical generation (``cold``) and
hint-mode previews (``hint``).
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

__all__ = [
    "CriterionBundle",
    "PreconditionFailure",
    "SpecBundle",
    "UnknownComponentError",
    "assemble",
    "assemble_criterion",
    "main",
]

USAGE = (
    "usage: hotdocs assemble <component-id> [--mode=cold|hint] "
    "[--repo-root=<dir>] [--format=json|text]"
)

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BACKTICKED = re.compile(r"`([^`]+)`")
_INTERNAL_SECTIONS = {"Rationale", "Open questions", "Change log"}
_LOADED: dict = {}


class PreconditionFailure(Exception):
    """The corpus is not in a state a bundle can be assembled from."""


class UnknownComponentError(KeyError, ValueError):
    """No component in the corpus has the requested id."""


class _ReadOnlyMapping(Mapping):
    """Lets a dataclass also be read as a read-only mapping of its fields."""

    def _field_names(self):
        return [f.name for f in fields(self)]

    def __getitem__(self, key):
        if key not in self._field_names():
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._field_names())

    def __len__(self):
        return len(fields(self))


@dataclass
class SpecBundle(_ReadOnlyMapping):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: dict | None = None


@dataclass
class CriterionBundle(_ReadOnlyMapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Dependency access helpers
# --------------------------------------------------------------------------


def _get(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _resolve_dir(repo_root: Path, rel: str) -> Path:
    local = repo_root / rel
    return local if local.is_dir() else _tool_root() / rel


def _module_file(directory: Path, module_name: str):
    flat = directory / f"{module_name}.py"
    if flat.is_file():
        return flat
    package = directory / module_name / "__init__.py"
    return package if package.is_file() else None


def _exec_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _tool_module(repo_root: Path, slug: str):
    module_name = slug.replace("-", "_")
    path = _module_file(_resolve_dir(repo_root, f"gen/{slug}"), module_name)
    key = str(path)
    if key not in _LOADED:
        _LOADED[key] = _exec_module(module_name, path)
    return _LOADED[key]


def _load_corpus(repo_root: Path):
    linter = _tool_module(repo_root, "spec-linter")
    graph_engine = _tool_module(repo_root, "graph-query-engine")
    report = linter.lint(None, repo_root)
    failures = _get(report, "hard_failures")
    if failures:
        raise PreconditionFailure(
            f"corpus under {repo_root} is not lint-clean: {failures} hard failure(s)"
        )
    corpus = linter.load_corpus(repo_root)
    graph_engine.load_views(_get(corpus, "graph"), repo_root)
    return corpus


def _component(corpus, component_id: str):
    comp = _get(_get(corpus, "components"), component_id.removeprefix("comp-"))
    if comp is None:
        raise UnknownComponentError(component_id)
    return comp


def _frontmatter(comp):
    return _get(_get(comp, "root"), "frontmatter")


# --------------------------------------------------------------------------
# Text assembly
# --------------------------------------------------------------------------


def _join(texts) -> str:
    stripped = (t.strip() for t in texts)
    return "\n\n".join(t for t in stripped if t)


def _without_internal_sections(body: str) -> str:
    kept, skipping = [], False
    for line in body.splitlines():
        if line.startswith("## "):
            skipping = line[3:].strip() in _INTERNAL_SECTIONS
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


def _spec_text(comp) -> str:
    requirements = _get(comp, "requirements")
    root_body = _without_internal_sections(_get(_get(comp, "root"), "body", ""))
    return _join([root_body] + [_get(requirements[k], "body") for k in sorted(requirements)])


def _interface_docs(comp) -> list:
    docs = [_get(comp, "interface_cli"), _get(comp, "interface_library")]
    for key in ("interface_data", "interface_guarantees"):
        group = _get(comp, key)
        docs.extend(group[k] for k in sorted(group))
    return [d for d in docs if d is not None]


def _target_interface(repo_root: Path, comp):
    text = _join(_get(d, "body") for d in _interface_docs(comp))
    named = []
    for line in _get(_get(comp, "interface_library"), "body", "").splitlines():
        if line.startswith("Implements:"):
            named.extend(_BACKTICKED.findall(line))
    for rel in named:
        path = repo_root / rel
        if not path.is_file():
            raise PreconditionFailure(f"Implements: names `{rel}`, which does not exist")
        text += f"\n\n## Implements: {rel}\n\n{path.read_text(encoding='utf-8')}"
    return text, named


def _type_owners(corpus) -> dict:
    owners: dict = {}
    components = _get(corpus, "components")
    for name in sorted(components):
        for stem, doc in _get(components[name], "interface_data").items():
            owners.setdefault(stem, []).append((name, doc))
    return owners


def _dependency_interfaces(corpus, comp):
    owners = _type_owners(corpus)
    components = _get(corpus, "components")
    entries, type_rels = {}, set()
    for dep_id in _get(_frontmatter(comp), "depends_on", []):
        dep = _get(components, dep_id.removeprefix("comp-"))
        texts = [_get(doc, "body") for doc in _interface_docs(dep)]
        own = set(_get(dep, "interface_data"))
        names = sorted({n for t in texts for n in _IDENTIFIER.findall(t)} - own)
        for name in names:
            found = owners.get(name, [])
            if len(found) == 1:
                owner, doc = found[0]
                texts.append(
                    f"## Type: {name} (owned by comp-{owner})\n\n{_get(doc, 'body').strip()}"
                )
                type_rels.add(_get(doc, "rel_path"))
        entries[dep_id] = _join(texts)
    return entries, type_rels


def _glossary(repo_root: Path) -> str:
    return (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------
# Files, code directories and hashing
# --------------------------------------------------------------------------


def _rel(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _md_rels(repo_root: Path, rel_dir: str) -> list:
    return [_rel(repo_root, p) for p in (repo_root / rel_dir).rglob("*.md")]


def _code_files(directory: Path) -> list:
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file()
        and not p.name.startswith(".")
        and "__pycache__" not in p.relative_to(directory).parts
    )


def _code_rel(dep, slug: str) -> str:
    fm = _frontmatter(dep)
    if _get(fm, "sealed"):
        return _get(fm, "source_path").rstrip("/") + "/"
    return f"gen/{slug}/"


def _bundle_hash(repo_root: Path, mode: str, rels) -> str:
    digest = hashlib.sha256()
    digest.update(mode.encode("utf-8") + b"\0")
    for rel in sorted(set(rels)):
        path = repo_root / rel
        if path.is_file():
            digest.update(rel.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def _usage_card(repo_root: Path, slug: str, code_rel: str) -> str:
    module_name = slug.replace("-", "_")
    path = _module_file(_resolve_dir(repo_root, code_rel), module_name)
    if path is None:
        return ""
    module = _exec_module(module_name, path)
    namespace = vars(module)
    lines = [f"Importable as: `{module_name}` (module path `{code_rel}`)."]
    for name in sorted(namespace):
        obj = namespace[name]
        if (
            name.startswith("_")
            or not (inspect.isfunction(obj) or inspect.isclass(obj))
            or obj.__module__ != module_name
        ):
            continue
        try:
            signature = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        line = f"- `{name}{signature}`"
        doc = inspect.cleandoc(obj.__doc__ or "")
        if doc:
            line += f" -- {doc.splitlines()[0]}"
        lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------


def assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle:
    """Assemble ``component_id``'s full generation input."""
    repo_root = Path(repo_root)
    corpus = _load_corpus(repo_root)
    comp = _component(corpus, component_id)
    slug = component_id.removeprefix("comp-")
    fm = _frontmatter(comp)
    components = _get(corpus, "components")
    graph = _get(corpus, "graph")

    target_dir = f"specs/components/{slug}"
    rels = {f"{target_dir}/component.md", f"{target_dir}/constraints.md", "specs/glossary.md"}
    rels.update(_md_rels(repo_root, f"{target_dir}/requirements"))
    rels.update(_md_rels(repo_root, f"{target_dir}/interface"))

    interface, implemented = _target_interface(repo_root, comp)
    rels.update(implemented)

    dependency_interfaces, type_rels = _dependency_interfaces(corpus, comp)
    rels.update(type_rels)

    context, usage = {}, {}
    for dep_id in _get(fm, "depends_on", []):
        dep_slug = dep_id.removeprefix("comp-")
        code_rel = _code_rel(_get(components, dep_slug), dep_slug)
        rels.add(f"specs/components/{dep_slug}/component.md")
        rels.update(_md_rels(repo_root, f"specs/components/{dep_slug}/interface"))
        rels.update(_rel(repo_root, p) for p in _code_files(repo_root / code_rel))
        row = graph.execute(
            "SELECT purpose FROM component_context WHERE component_id = ?", [dep_id]
        ).fetchone()
        context[dep_id] = row[0].strip()
        usage[dep_id] = _usage_card(repo_root, dep_slug, code_rel)

    variables = {}
    id_index = _get(corpus, "id_index")
    for var_id in _get(fm, "uses_var", []):
        doc = _get(id_index, var_id)
        variables[var_id] = Path(_get(doc, "path")).read_text(encoding="utf-8").strip()
        rels.add(_get(doc, "rel_path"))

    hint_code = None
    if mode == "hint":
        code_dir = repo_root / "gen" / slug
        files = _code_files(code_dir)
        hint_code = {
            p.relative_to(code_dir).as_posix(): p.read_bytes().decode("utf-8", "replace")
            for p in files
        }
        rels.update(_rel(repo_root, p) for p in files)

    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=_bundle_hash(repo_root, mode, rels),
        spec=_spec_text(comp),
        interface=interface,
        constraints=_join([_get(_get(comp, "constraints"), "body", "")]),
        dependency_interfaces=dependency_interfaces,
        dependency_context=context,
        dependency_usage=usage,
        vars=variables,
        glossary=_glossary(repo_root),
        hint_code=hint_code,
    )


def assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle:
    """Assemble the narrower bundle ``test-author`` sees for one criterion."""
    repo_root = Path(repo_root)
    corpus = _load_corpus(repo_root)
    comp = _component(corpus, component_id)
    criterion = _get(_get(comp, "acceptance"), criterion_id)
    covers = (
        _get(corpus, "graph")
        .execute(
            "SELECT target_id FROM edges WHERE source_id = ? AND edge_type = 'covers' "
            "ORDER BY target_id",
            [criterion_id],
        )
        .fetchone()[0]
    )
    interface, _ = _target_interface(repo_root, comp)
    dependency_interfaces, _ = _dependency_interfaces(corpus, comp)
    requirement = _get(_get(comp, "requirements"), covers)
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=_get(criterion, "body").strip(),
        requirement_text=_get(requirement, "body").strip(),
        interface=interface,
        glossary=_glossary(repo_root),
        dependency_interfaces=dependency_interfaces,
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    tokens = sys.argv[1:] if argv is None else list(argv)
    choices = {"--mode": ("cold", "hint"), "--format": ("json", "text"), "--repo-root": None}
    options = {"--mode": "cold", "--format": "text", "--repo-root": "."}
    positional = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        name, has_value, value = token.partition("=")
        if name in choices:
            if not has_value:
                if index + 1 == len(tokens):
                    return _usage_error(f"{name} requires a value")
                index += 1
                value = tokens[index]
            allowed = choices[name]
            if allowed is not None and value not in allowed:
                return _usage_error(
                    f"invalid value for {name}: {value!r} (choose from {', '.join(allowed)})"
                )
            options[name] = value
        elif token.startswith("-") or positional:
            return _usage_error(f"unrecognized argument: {token}")
        else:
            positional.append(token)
        index += 1
    if not positional:
        return _usage_error("missing <component-id>")
    try:
        bundle = assemble(positional[0], Path(options["--repo-root"]), options["--mode"])
    except PreconditionFailure as exc:
        print(f"precondition failure: {exc}", file=sys.stderr)
        return 1
    except UnknownComponentError:
        return _usage_error(f"unknown component id: {positional[0]}")
    if options["--format"] == "json":
        print(json.dumps(asdict(bundle), indent=2))
    else:
        print(f"{bundle.component_id} {bundle.spec_bundle_hash}")
    return 0
