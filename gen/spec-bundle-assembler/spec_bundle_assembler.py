"""Spec Bundle Assembler: builds a component's SpecBundle / CriterionBundle."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import inspect
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

_EXCLUDED_SECTIONS = {"Rationale", "Open questions", "Change log"}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BACKTICKED = re.compile(r"`([^`]*)`")


class PreconditionFailure(Exception):
    """Raised when a bundle cannot be assembled (R-ASSEMBLE-005/014/016)."""


class UnknownComponentError(ValueError):
    """Raised when the component id names no component in the corpus."""


class _MappingMixin(Mapping):
    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


@dataclass
class SpecBundle(_MappingMixin):
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
    hint_code: object = None


@dataclass
class CriterionBundle(_MappingMixin):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)
    testing: str = ""


# ---------------------------------------------------------------- helpers


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _module_file(name: str, directory: Path):
    flat = directory / f"{name}.py"
    if flat.is_file():
        return flat
    init = directory / name / "__init__.py"
    if init.is_file():
        return init
    return None


def _load_path(name: str, path: Path, package_dir=None):
    for key in [k for k in sys.modules if k.startswith(name + ".")]:
        del sys.modules[key]
    if package_dir is None:
        spec = importlib.util.spec_from_file_location(name, path)
    else:
        spec = importlib.util.spec_from_file_location(
            name, path, submodule_search_locations=[str(package_dir)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_module(name: str, directory: Path):
    path = _module_file(name, directory)
    package_dir = None if path.name == f"{name}.py" else path.parent
    return _load_path(name, path, package_dir)


def _dependency_module(slug: str, repo_root: Path):
    directory = repo_root / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    return _load_module(slug.replace("-", "_"), directory)


def _body(doc) -> str:
    return (_get(doc, "body") or "").strip()


def _join(parts) -> str:
    return "\n\n".join(p.strip() for p in parts if p.strip())


def _strip_sections(body: str) -> str:
    out = []
    skip = False
    for line in body.split("\n"):
        if line.startswith("## "):
            skip = line[3:].strip() in _EXCLUDED_SECTIONS
        if not skip:
            out.append(line)
    return "\n".join(out)


def _code_files(directory: Path):
    result = []
    for p in directory.rglob("*"):
        rel = p.relative_to(directory)
        if p.is_file() and not p.name.startswith(".") and "__pycache__" not in rel.parts:
            result.append(p)
    return sorted(result)


class _Ctx:
    def __init__(self, component_id, repo_root):
        self.repo_root = Path(repo_root)
        gqe_dir = self.repo_root
        linter = _dependency_module("spec-linter", gqe_dir)
        _dependency_module("graph-query-engine", gqe_dir)
        report = linter.lint(None, self.repo_root)
        failures = _get(report, "hard_failures")
        if failures:
            raise PreconditionFailure(
                f"corpus is not lint-clean: {failures} hard failure(s)"
            )
        self.corpus = linter.load_corpus(self.repo_root)
        self.components = _get(self.corpus, "components")
        self.by_id = {
            _get(_get(c, "root"), "doc_id"): key
            for key, c in self.components.items()
            if _get(c, "root") is not None
        }
        if component_id not in self.by_id:
            raise UnknownComponentError(f"unknown component id: {component_id}")
        self.slug = self.by_id[component_id]
        self.comp = self.components[self.slug]
        self.root = _get(self.comp, "root")
        self.frontmatter = _get(self.root, "frontmatter") or {}
        self.files: dict = {}

    def comp_dir(self, key) -> Path:
        return self.repo_root / "specs" / "components" / key

    def add(self, path: Path, rel=None):
        if rel is None:
            rel = path.relative_to(self.repo_root).as_posix()
        self.files[rel] = path

    def add_md_tree(self, directory: Path):
        for p in directory.rglob("*.md"):
            if p.is_file():
                self.add(p)

    # -- interface content (R-ASSEMBLE-002, R-ASSEMBLE-016)
    def interface_parts(self, comp, key):
        docs = [_get(comp, "interface_cli"), _get(comp, "interface_library")]
        data = _get(comp, "interface_data")
        docs += [data[k] for k in sorted(data)]
        guarantees = _get(comp, "interface_guarantees")
        docs += [guarantees[k] for k in sorted(guarantees)]
        parts = [_body(d) for d in docs if d is not None]
        assets_dir = self.comp_dir(key) / "interface" / "assets"
        for p in sorted(assets_dir.glob("*.md"), key=lambda q: q.name):
            parts.append(p.read_text(encoding="utf-8").strip())
        return parts

    # -- R-ASSEMBLE-014
    def implements(self) -> str:
        library = _get(self.comp, "interface_library")
        paths = []
        for line in (_get(library, "body") or "").splitlines():
            if line.startswith("Implements:"):
                paths += _BACKTICKED.findall(line)
        out = ""
        for rel in paths:
            path = self.repo_root / rel
            if not path.is_file():
                raise PreconditionFailure(f"Implements: document not found: {rel}")
            self.add(path, Path(rel).as_posix())
            out += f"\n\n## Implements: {rel}\n\n" + path.read_text(encoding="utf-8").strip()
        return out

    def target_interface(self) -> str:
        return _join(self.interface_parts(self.comp, self.slug)) + self.implements()

    # -- R-ASSEMBLE-016
    def guidance(self):
        kinds = sorted({a.split(":", 1)[0] for a in _get(self.frontmatter, "assets", [])})
        result = []
        for kind in kinds:
            module = f"kind_{kind.replace('-', '_')}"
            rel = f"gen/kind-{kind}/{module}.py"
            path = self.repo_root / rel
            if not path.is_file():
                path = _tool_root() / rel
            if not path.is_file():
                raise PreconditionFailure(f"unknown asset kind: {kind}")
            self.add(path, rel)
            adapter = _load_path(module, path)
            result.append((kind, adapter.guidance()))
        return result

    # -- R-ASSEMBLE-002, R-ASSEMBLE-013
    def depends_on(self):
        return _get(self.frontmatter, "depends_on", [])

    def dependency_interfaces(self) -> dict:
        owners: dict = {}
        for key in sorted(self.components):
            for type_name in _get(self.components[key], "interface_data"):
                owners.setdefault(type_name, []).append(key)
        result = {}
        for dep in self.depends_on():
            key = self.by_id[dep]
            comp = self.components[key]
            dep_root = _get(comp, "root")
            self.add(self.repo_root / _get(dep_root, "rel_path"))
            self.add_md_tree(self.comp_dir(key) / "interface")
            parts = self.interface_parts(comp, key)
            own = _get(comp, "interface_data")
            for name in sorted(set(_IDENT.findall("\n".join(parts)))):
                found = owners.get(name, [])
                if name not in own and len(found) == 1:
                    owner = self.components[found[0]]
                    doc = _get(owner, "interface_data")[name]
                    owner_id = _get(_get(owner, "root"), "doc_id")
                    self.add(self.repo_root / _get(doc, "rel_path"))
                    parts.append(f"## Type: {name} (owned by {owner_id})\n\n{_body(doc)}")
            result[dep] = _join(parts)
        return result

    def glossary(self) -> str:
        path = self.repo_root / "specs" / "glossary.md"
        self.add(path)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
        return ""


def _usage_card(ctx: _Ctx, key: str, dep_root) -> str:
    module_name = key.replace("-", "_")
    source = _get(_get(dep_root, "frontmatter") or {}, "source_path")
    rel_dir = source.rstrip("/") + "/" if source else f"gen/{key}/"
    directory = ctx.repo_root / rel_dir
    for p in _code_files(directory):
        ctx.add(p)
    if _module_file(module_name, directory) is None:
        return ""
    module = _load_module(module_name, directory)
    lines = [f"Importable as: `{module_name}` (module path `{rel_dir}`)."]
    members = vars(module)
    for name in sorted(members):
        obj = members[name]
        if name.startswith("_") or not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        owner = getattr(obj, "__module__", "") or ""
        if owner != module_name and not owner.startswith(module_name + "."):
            continue
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            continue
        line = f"- `{name}{sig}`"
        doc = (obj.__doc__ or "").strip()
        if doc:
            line += " -- " + doc.splitlines()[0].strip()
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------- library


def assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle:
    """Assemble a component's full generation input (R-ASSEMBLE-001..016)."""
    ctx = _Ctx(component_id, repo_root)
    comp_dir = ctx.comp_dir(ctx.slug)
    ctx.add(comp_dir / "component.md")
    ctx.add(comp_dir / "constraints.md")
    ctx.add_md_tree(comp_dir / "requirements")
    ctx.add_md_tree(comp_dir / "interface")

    requirements = _get(ctx.comp, "requirements")
    spec = _join(
        [_strip_sections(_get(ctx.root, "body") or "")]
        + [_body(requirements[k]) for k in sorted(requirements)]
    )
    interface = ctx.target_interface()
    for kind, guide in ctx.guidance():
        interface += "\n\n## Asset kind: " + kind + "\n\n" + (_get(guide, "generator") or "").strip()
    constraints_doc = _get(ctx.comp, "constraints")
    constraints = _body(constraints_doc) if constraints_doc is not None else ""

    dependency_interfaces = ctx.dependency_interfaces()
    graph = _get(ctx.corpus, "graph")
    dependency_context = {}
    dependency_usage = {}
    for dep in ctx.depends_on():
        row = graph.execute(
            "SELECT purpose FROM component_context WHERE component_id = ?", [dep]
        ).fetchone()
        dependency_context[dep] = (row[0] or "").strip()
        key = ctx.by_id[dep]
        dependency_usage[dep] = _usage_card(ctx, key, _get(ctx.components[key], "root"))

    id_index = _get(ctx.corpus, "id_index")
    var_texts = {}
    for var_id in _get(ctx.frontmatter, "uses_var", []):
        doc = id_index[var_id]
        ctx.add(ctx.repo_root / _get(doc, "rel_path"))
        var_texts[var_id] = _body(doc)

    glossary = ctx.glossary()

    hint_code = None
    if mode == "hint":
        gen_dir = ctx.repo_root / "gen" / ctx.slug
        hint_code = {}
        for p in _code_files(gen_dir):
            ctx.add(p)
            hint_code[p.relative_to(gen_dir).as_posix()] = p.read_bytes().decode(
                "utf-8", "replace"
            )

    digest = hashlib.sha256()
    digest.update(mode.encode("utf-8") + b"\0")
    for rel in sorted(ctx.files):
        path = ctx.files[rel]
        if path.is_file():
            digest.update(rel.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")

    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + digest.hexdigest(),
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


def assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle:
    """Assemble one acceptance criterion's narrower bundle (R-ASSEMBLE-009)."""
    ctx = _Ctx(component_id, repo_root)
    criterion = _get(ctx.comp, "acceptance")[criterion_id]
    graph = _get(ctx.corpus, "graph")
    covers = graph.execute(
        "SELECT target_id FROM edges WHERE source_id = ? AND edge_type = 'covers' "
        "ORDER BY target_id",
        [criterion_id],
    ).fetchone()[0]
    requirement = _get(ctx.comp, "requirements")[covers]
    interface = ctx.target_interface()

    testing_path = ctx.comp_dir(ctx.slug) / "testing.md"
    text = testing_path.read_text(encoding="utf-8") if testing_path.is_file() else ""
    testing = text
    first = text.split("\n", 1)[0]
    if first.startswith("Uses:"):
        for rel in _BACKTICKED.findall(first):
            path = ctx.repo_root / rel
            if not path.is_file():
                raise PreconditionFailure(f"Uses: document not found: {rel}")
            testing += f"\n## Uses: {rel}\n\n{path.read_text(encoding='utf-8')}"
    for kind, guide in ctx.guidance():
        testing += "\n## Asset kind: " + kind + "\n\n" + (_get(guide, "test_author") or "").strip()

    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=_body(criterion),
        requirement_text=_body(requirement),
        interface=interface,
        glossary=ctx.glossary(),
        dependency_interfaces=ctx.dependency_interfaces(),
        testing=testing,
    )


# ---------------------------------------------------------------- CLI


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def _parser() -> _Parser:
    parser = _Parser(prog="hotdocs assemble", add_help=False, allow_abbrev=False)
    parser.add_argument("component_id")
    parser.add_argument("--mode", choices=["cold", "hint"], default="cold")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def _usage_error(parser, cause) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    sys.stderr.write(parser.format_usage())
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except _UsageError as exc:
        return _usage_error(parser, exc)
    try:
        bundle = assemble(args.component_id, Path(args.repo_root), args.mode)
    except UnknownComponentError as exc:
        return _usage_error(parser, exc)
    except PreconditionFailure as exc:
        print(f"precondition failure: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(dataclasses.asdict(bundle), indent=2))
    else:
        print(f"component_id: {bundle.component_id}")
        print(f"spec_bundle_hash: {bundle.spec_bundle_hash}")
        print(f"mode: {args.mode}")
        print("dependencies: " + ", ".join(bundle.dependency_interfaces))
    return 0
