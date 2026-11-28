"""Spec Bundle Assembler: assembles a component's generation input into one payload."""

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
from dataclasses import dataclass, field, fields
from pathlib import Path

__all__ = [
    "PreconditionFailure",
    "UnknownComponentError",
    "SpecBundle",
    "CriterionBundle",
    "assemble",
    "assemble_criterion",
    "main",
]

_DROPPED_SECTIONS = {"Rationale", "Open questions", "Change log"}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BACKTICKED = re.compile(r"`([^`]+)`")


class PreconditionFailure(Exception):
    """Assembly refused: a precondition of the corpus does not hold."""


class UnknownComponentError(KeyError):
    """No component in the corpus has the given id."""


class _ReadOnlyMapping(Mapping):
    def __getitem__(self, key):
        return {f.name: getattr(self, f.name) for f in fields(self)}[key]

    def __iter__(self):
        return iter([f.name for f in fields(self)])

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
    hint_code: object = None
    spec_bundle_parts: dict = field(default_factory=dict)


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
    testing: str = ""


# ---------------------------------------------------------------- helpers


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _locate(repo_root, rel):
    path = Path(repo_root) / rel
    if path.exists():
        return path
    return _tool_root() / rel


def _module_file(directory, name):
    for candidate in (directory / f"{name}.py", directory / name / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _load_file(name, path):
    for key in [k for k in sys.modules if k.startswith(name + ".")]:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dep(repo_root, slug):
    name = slug.replace("-", "_")
    return _load_file(name, _module_file(_locate(repo_root, f"gen/{slug}"), name))


def _read_text(path):
    return path.read_bytes().decode("utf-8") if path.is_file() else ""


def _body(doc):
    return _get(doc, "body") or ""


def _join(texts):
    return "\n\n".join(s for s in (t.strip() for t in texts) if s)


def _cut(data, keep):
    """Cut every `## ` section whose title `keep` rejects, heading to next `## ` or EOF."""
    out = []
    cutting = False
    for line in data.splitlines(keepends=True):
        if line.startswith(b"## "):
            cutting = not keep(line[3:].strip().decode("utf-8"))
        if not cutting:
            out.append(line)
    return b"".join(out)


def _keep_target(title):
    return title not in _DROPPED_SECTIONS


def _keep_purpose(title):
    return title == "Purpose"


def _add(entries, repo_root, rel, keep=None):
    path = Path(repo_root) / rel
    if path.is_file():
        data = path.read_bytes()
        entries[rel] = _cut(data, keep) if keep else data


def _add_md_tree(entries, repo_root, rel_dir):
    root = Path(repo_root)
    for path in sorted((root / rel_dir).rglob("*.md")):
        entries[path.relative_to(root).as_posix()] = path.read_bytes()


def _code_files(repo_root, rel_dir):
    directory = Path(repo_root) / rel_dir
    return [
        p
        for p in sorted(directory.rglob("*"))
        if p.is_file()
        and not p.name.startswith(".")
        and "__pycache__" not in p.relative_to(directory).parts
    ]


def _digest(mode, entries):
    h = hashlib.sha256(mode.encode("utf-8") + b"\0")
    for path in sorted(entries):
        h.update(path.encode("utf-8") + b"\0" + entries[path] + b"\0")
    return "sha256:" + h.hexdigest()


def _frontmatter(comp):
    return _get(_get(comp, "root"), "frontmatter", {}) or {}


def _find(corpus, component_id):
    for name, comp in _get(corpus, "components", {}).items():
        if _get(_get(comp, "root"), "doc_id") == component_id:
            return name, comp
    raise UnknownComponentError(f"unknown component id: {component_id}")


def _prepare(repo_root):
    linter = _load_dep(repo_root, "spec-linter")
    report = linter.lint(None, repo_root)
    failures = [f for f in _get(report, "findings", []) if _get(f, "severity") == "fail"]
    if failures:
        raise PreconditionFailure(
            f"corpus is not lint-clean: {len(failures)} hard failure(s)"
        )
    corpus = linter.load_corpus(repo_root)
    graph = _get(corpus, "graph")
    _load_dep(repo_root, "graph-query-engine").load_views(graph, repo_root)
    return corpus, graph


def _named_docs(repo_root, lines, prefix):
    out = []
    for line in lines:
        if line.startswith(prefix):
            for rel in _BACKTICKED.findall(line):
                path = Path(repo_root) / rel
                if not path.is_file():
                    raise PreconditionFailure(f"{prefix} document not found: {rel}")
                out.append((rel, path.read_bytes()))
    return out


def _interface_texts(repo_root, name, comp):
    docs = [_get(comp, "interface_cli"), _get(comp, "interface_library")]
    data = _get(comp, "interface_data", {})
    guarantees = _get(comp, "interface_guarantees", {})
    docs += [data[k] for k in sorted(data)]
    docs += [guarantees[k] for k in sorted(guarantees)]
    texts = [_body(d) for d in docs]
    assets_dir = Path(repo_root) / "specs" / "components" / name / "interface" / "assets"
    texts += [p.read_bytes().decode("utf-8") for p in sorted(assets_dir.glob("*.md"))]
    return texts


def _target_interface(repo_root, name, comp, entries):
    interface = _join(_interface_texts(repo_root, name, comp))
    lines = _body(_get(comp, "interface_library")).splitlines()
    for rel, data in _named_docs(repo_root, lines, "Implements:"):
        entries[rel] = data
        interface += f"\n\n## Implements: {rel}\n\n{data.decode('utf-8')}"
    return interface


def _type_owners(corpus):
    owners = {}
    components = _get(corpus, "components", {})
    for cname in sorted(components):
        comp = components[cname]
        owner_id = _get(_get(comp, "root"), "doc_id")
        for stem, doc in _get(comp, "interface_data", {}).items():
            owners.setdefault(stem, []).append((owner_id, doc))
    return owners


def _dep_interface(repo_root, dname, dcomp, owners, entries):
    texts = _interface_texts(repo_root, dname, dcomp)
    owned = _get(dcomp, "interface_data", {})
    for ident in sorted(set(_IDENT.findall("\n".join(texts)))):
        found = owners.get(ident, [])
        if ident not in owned and len(found) == 1:
            owner_id, doc = found[0]
            texts.append(f"## Type: {ident} (owned by {owner_id})\n\n{_body(doc).strip()}")
            _add(entries, repo_root, _get(doc, "rel_path"))
    return _join(texts)


def _declared(fm, key):
    return sorted({str(item).split(":", 1)[0] for item in _get(fm, key, []) or []})


def _adapters(repo_root, fm, key, prefix, label, entries):
    loaded = []
    for name in _declared(fm, key):
        module_name = f"{prefix}_{name.replace('-', '_')}"
        rel = f"gen/{prefix}-{name}/{module_name}.py"
        path = _locate(repo_root, rel)
        if not path.is_file():
            raise PreconditionFailure(f"unknown {label}: {name}")
        entries[rel] = path.read_bytes()
        loaded.append((name, _load_file(module_name, path)))
    return loaded


def _code_dir(dname, dfm):
    return str(_get(dfm, "source_path") or f"gen/{dname}").strip("/") + "/"


def _usage_card(repo_root, dname, code_rel):
    name = dname.replace("-", "_")
    path = _module_file(Path(repo_root) / code_rel, name)
    if path is None:
        return ""
    module = _load_file(name, path)
    lines = [f"Importable as: `{name}` (module path `{code_rel}`)."]
    members = module.__dict__
    for attr in sorted(members):
        obj = members[attr]
        if attr.startswith("_") or not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        if not (str(getattr(obj, "__module__", "")) + ".").startswith(name + "."):
            continue
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            continue
        doc = (obj.__doc__ or "").strip().splitlines()
        lines.append(f"- `{attr}{sig}`" + (f" -- {doc[0].strip()}" if doc else ""))
    return "\n".join(lines)


def _purpose(graph, dep_id):
    rows = graph.execute(
        "SELECT purpose FROM component_context WHERE component_id = ?", [dep_id]
    ).fetchall()
    return "".join(r[0] or "" for r in rows).strip()


# ---------------------------------------------------------------- library


def assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle:
    """Assemble the SpecBundle for one component."""
    repo_root = Path(repo_root)
    corpus, graph = _prepare(repo_root)
    name, comp = _find(corpus, component_id)
    fm = _frontmatter(comp)
    base = f"specs/components/{name}"
    entries = {}
    code_entries = {}

    _add(entries, repo_root, f"{base}/component.md", _keep_target)
    _add(entries, repo_root, f"{base}/constraints.md")
    _add_md_tree(entries, repo_root, f"{base}/requirements")
    _add_md_tree(entries, repo_root, f"{base}/interface")

    requirements = _get(comp, "requirements", {})
    root_body = _cut(_body(_get(comp, "root")).encode("utf-8"), _keep_target).decode("utf-8")
    spec = _join([root_body] + [_body(requirements[k]) for k in sorted(requirements)])

    interface = _target_interface(repo_root, name, comp, entries)
    for kind, module in _adapters(repo_root, fm, "assets", "kind", "asset kind", entries):
        generator = str(_get(module.guidance(), "generator")).strip()
        interface += "\n\n## Asset kind: " + kind + "\n\n" + generator
    _adapters(repo_root, fm, "drivers", "driver", "test driver", entries)

    owners = _type_owners(corpus)
    dependency_interfaces, dependency_context, dependency_usage = {}, {}, {}
    for dep_id in _get(fm, "depends_on", []) or []:
        dname, dcomp = _find(corpus, dep_id)
        dbase = f"specs/components/{dname}"
        _add(entries, repo_root, f"{dbase}/component.md", _keep_purpose)
        _add_md_tree(entries, repo_root, f"{dbase}/interface")
        dependency_interfaces[dep_id] = _dep_interface(repo_root, dname, dcomp, owners, entries)
        dependency_context[dep_id] = _purpose(graph, dep_id)
        code_rel = _code_dir(dname, _frontmatter(dcomp))
        for path in _code_files(repo_root, code_rel):
            code_entries[path.relative_to(repo_root).as_posix()] = path.read_bytes()
        dependency_usage[dep_id] = _usage_card(repo_root, dname, code_rel)

    var_texts = {}
    id_index = _get(corpus, "id_index", {})
    for var_id in _get(fm, "uses_var", []) or []:
        doc = id_index[var_id]
        var_texts[var_id] = _body(doc).strip()
        _add(entries, repo_root, _get(doc, "rel_path"))

    _add(entries, repo_root, "specs/glossary.md")
    glossary = _read_text(repo_root / "specs" / "glossary.md").strip()

    hint_code = None
    if mode == "hint":
        hint_code = {}
        hint_dir = repo_root / "gen" / name
        for path in _code_files(repo_root, f"gen/{name}"):
            data = path.read_bytes()
            entries[path.relative_to(repo_root).as_posix()] = data
            hint_code[path.relative_to(hint_dir).as_posix()] = data.decode("utf-8", errors="replace")

    spec_only = {p: b for p, b in entries.items() if p not in code_entries}
    everything = {**spec_only, **code_entries}

    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=_digest(mode, everything),
        spec=spec,
        interface=interface,
        constraints=_body(_get(comp, "constraints")).strip(),
        dependency_interfaces=dependency_interfaces,
        dependency_context=dependency_context,
        dependency_usage=dependency_usage,
        vars=var_texts,
        glossary=glossary,
        hint_code=hint_code,
        spec_bundle_parts={
            "spec": _digest(mode, spec_only),
            "dependency_code": _digest(mode, code_entries),
        },
    )


def assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle:
    """Assemble the narrower CriterionBundle for one acceptance criterion."""
    repo_root = Path(repo_root)
    corpus, graph = _prepare(repo_root)
    name, comp = _find(corpus, component_id)
    fm = _frontmatter(comp)
    scratch = {}

    criterion = _get(comp, "acceptance", {})[criterion_id]
    covers = graph.execute(
        "SELECT target_id FROM edges WHERE source_id = ? AND edge_type = 'covers'",
        [criterion_id],
    ).fetchall()[0][0]
    requirement = _get(comp, "requirements", {})[covers]

    interface = _target_interface(repo_root, name, comp, scratch)

    text = _read_text(repo_root / "specs" / "components" / name / "testing.md")
    uses = _named_docs(repo_root, [text.split("\n", 1)[0]], "Uses:")
    testing = text + "".join(f"\n## Uses: {rel}\n\n{data.decode('utf-8')}" for rel, data in uses)
    for kind, module in _adapters(repo_root, fm, "assets", "kind", "asset kind", scratch):
        guide = str(_get(module.guidance(), "test_author")).strip()
        testing += "\n## Asset kind: " + kind + "\n\n" + guide
    for driver, module in _adapters(repo_root, fm, "drivers", "driver", "test driver", scratch):
        guide = str(_get(module.guidance(), "test_author")).strip()
        testing += "\n## Test driver: " + driver + "\n\n" + guide

    owners = _type_owners(corpus)
    dependency_interfaces = {}
    for dep_id in _get(fm, "depends_on", []) or []:
        dname, dcomp = _find(corpus, dep_id)
        dependency_interfaces[dep_id] = _dep_interface(repo_root, dname, dcomp, owners, scratch)

    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=_body(criterion).strip(),
        requirement_text=_body(requirement).strip(),
        interface=interface,
        glossary=_read_text(repo_root / "specs" / "glossary.md").strip(),
        dependency_interfaces=dependency_interfaces,
        testing=testing,
    )


# ---------------------------------------------------------------- CLI


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def _parser():
    parser = _Parser(prog="hotdocs assemble", add_help=False, allow_abbrev=False)
    parser.add_argument("component_id")
    parser.add_argument("--mode", choices=["cold", "hint"], default="cold")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def _usage(parser, cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(parser.format_usage(), end="", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except _UsageError as exc:
        return _usage(parser, exc)
    try:
        bundle = assemble(args.component_id, Path(args.repo_root), args.mode)
    except UnknownComponentError as exc:
        return _usage(parser, exc.args[0])
    except PreconditionFailure as exc:
        print(f"precondition failure: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(dataclasses.asdict(bundle), indent=2))
    else:
        print(f"component_id: {bundle.component_id}")
        print(f"mode: {args.mode}")
        print(f"spec_bundle_hash: {bundle.spec_bundle_hash}")
        print(f"dependencies: {', '.join(bundle.dependency_interfaces)}")
        print(f"vars: {', '.join(bundle.vars)}")
        print(f"hint_code files: {len(bundle.hint_code or {})}")
    return 0
