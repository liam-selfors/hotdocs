"""Spec linter: mechanically validates a spec corpus against SPEC_GUIDELINES.md."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_FM_TYPES = ("component-root", "product", "architecture", "var", "decision")
_UNIT_TYPES = (
    "component-requirement",
    "component-interface-cli",
    "component-interface-library",
    "component-interface-data",
    "component-interface-guarantee",
    "component-acceptance",
    "component-constraints",
)
_REQUIRED = ("id", "title", "status", "owners")
_LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "builds_on")
_STATUSES = ("draft", "ratified", "deprecated")
_RFC2119 = re.compile(r"\b(MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)\b")
_KIND = re.compile(r"^Kind:\s*`?(compiled|generated-test|llm-judge)`?\s*$")
_ENTRY = re.compile(r"^\s*-\s+\*\*(.+?)\*\*(.*)$")
_LEAD = re.compile(r"^[\s\u2014-]+")
_BULLET = re.compile(r"^\s*[-*]\s+[*`_]*([A-Za-z_]+)[*`_]*\s*:\s*[*`_]*\s*(.*)$")
_WORD = re.compile(r"[A-Za-z][\w-]*")
_DECISION = re.compile(r"\bD\d+\b")
_BOUNDED = re.compile(r"bounded[- ]context", re.IGNORECASE)
_CS_HEADING = re.compile(r"^###\s+(CS-[A-Za-z0-9-]+)")
_COVERS_MSG = {
    "R-": "Covers: '{0}' looks like an R-id but no such requirement exists",
    "P-": "Covers: '{0}' looks like a P-id but no such capability exists",
}
_COVERS_NEITHER = "Covers: '{0}' is neither an R-id nor a P-id"
_USAGE = "usage: hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]"

_LOADED: dict = {}


# --------------------------------------------------------------------------
# Report types
# --------------------------------------------------------------------------


@dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    rationale: Any = None

    def to_json(self) -> dict:
        data = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }
        if self.rationale is not None:
            data["rationale"] = self.rationale
        return data


@dataclass
class LintReport:
    findings: list = field(default_factory=list)
    strict: bool = False

    @property
    def hard_failures(self) -> int:
        return sum(
            1
            for f in self.findings
            if f.severity == "fail" or (self.strict and f.severity == "warn")
        )

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warn")

    @property
    def skipped(self) -> int:
        return sum(1 for f in self.findings if f.severity == "skipped")

    def to_json(self) -> dict:
        return {
            "findings": [f.to_json() for f in self.findings],
            "summary": {
                "hard_failures": self.hard_failures,
                "warnings": self.warnings,
                "skipped": self.skipped,
            },
        }


# --------------------------------------------------------------------------
# Dependency loading
# --------------------------------------------------------------------------


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_dep(repo_root, slug, module_name):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    pkg = base / module_name / "__init__.py"
    target = pkg if pkg.is_file() else base / f"{module_name}.py"
    key = str(target)
    if key not in _LOADED:
        locations = [str(pkg.parent)] if target == pkg else None
        spec = importlib.util.spec_from_file_location(
            module_name, target, submodule_search_locations=locations
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        _LOADED[key] = module
    return _LOADED[key]


def __getattr__(name):
    if name == "load_corpus":
        return _load_dep(_tool_root(), "corpus-loader", "corpus_loader").load_corpus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


class _Ctx:
    def __init__(self, corpus, repo_root, judge):
        self.repo_root = repo_root
        self.judge = judge
        self.docs = list(_get(corpus, "docs", []))
        self.components = dict(_get(corpus, "components", {}))
        self.glossary_defs = dict(_get(corpus, "glossary_defs", {}))
        self.glossary_files = list(_get(corpus, "glossary_files", []))
        self.graph = _get(corpus, "graph")
        self.by_id = {
            _get(d, "doc_id"): d for d in self.docs if _get(d, "doc_type") in _FM_TYPES
        }

    def of_type(self, *types):
        return [d for d in self.docs if _get(d, "doc_type") in types]

    def text(self, doc):
        return Path(_get(doc, "path")).read_text(encoding="utf-8")

    def lines(self, doc):
        return self.text(doc).splitlines()

    def query(self, sql):
        return self.graph.execute(sql).fetchall()

    def fm(self, doc):
        return _get(doc, "frontmatter", {})


def _rel(doc):
    return _get(doc, "rel_path")


def _relpath(path, repo_root):
    return Path(
        os.path.relpath(Path(path).resolve(), Path(repo_root).resolve())
    ).as_posix()


def _as_list(value):
    return value if isinstance(value, list) else []


def _field_line(lines, name):
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            break
        if line.startswith(name + ":"):
            return number
    return 1


def _section(lines, title):
    want = "## " + title.lower()
    start = next((i for i, l in enumerate(lines) if l.strip().lower() == want), None)
    if start is None:
        return 0, []
    body = []
    for i in range(start + 1, len(lines)):
        if re.match(r"^#{1,2}\s", lines[i]):
            break
        body.append((i + 1, lines[i]))
    return start + 1, body


def _overlap(local, gloss):
    gloss_tokens = set(re.findall(r"\w+", gloss.lower()))
    local_tokens = set(re.findall(r"\w+", local.lower()))
    return len(gloss_tokens & local_tokens) / max(len(gloss_tokens), 1)


def _fail(rule_id, file, line, message, severity="fail", rationale=None):
    return Finding(rule_id, severity, file, line, message, rationale)


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------


def _r001(ctx):
    out = []
    for doc in ctx.of_type(*_FM_TYPES):
        fm = ctx.fm(doc)
        lines = ctx.lines(doc)
        for name in _REQUIRED:
            if name not in fm:
                out.append(_fail("R-LINT-001", _rel(doc), 1,
                                 f"missing required frontmatter field '{name}'"))
        for name in _LIST_FIELDS:
            if name in fm and not isinstance(fm[name], list):
                out.append(_fail("R-LINT-001", _rel(doc), _field_line(lines, name),
                                 f"frontmatter field '{name}' must be a list"))
        if "sealed" in fm and not isinstance(fm["sealed"], bool):
            out.append(_fail("R-LINT-001", _rel(doc), _field_line(lines, "sealed"),
                             "frontmatter field 'sealed' must be a boolean"))
        if "status" in fm and fm["status"] not in _STATUSES:
            out.append(_fail("R-LINT-001", _rel(doc), _field_line(lines, "status"),
                             f"frontmatter field 'status' must be one of "
                             f"{', '.join(_STATUSES)}, not '{fm['status']}'"))
    return out


def _r002(ctx):
    out = []
    for doc in ctx.of_type(*_FM_TYPES):
        fm = ctx.fm(doc)
        if fm.get("status") != "ratified":
            continue
        lines = ctx.lines(doc)
        heading, body = _section(lines, "Open questions")
        if any(text.strip() for _, text in body):
            out.append(_fail("R-LINT-002", _rel(doc), heading,
                             "ratified spec has a non-empty Open questions section"))
        if not fm.get("last_ratified_commit"):
            out.append(_fail("R-LINT-002", _rel(doc), _field_line(lines, "status"),
                             "ratified spec lacks last_ratified_commit"))
    return out


def _r003(ctx):
    out = []
    rows = ctx.query(
        "SELECT DISTINCT e.source_id, e.target_id, e.edge_type, n.id IS NULL "
        "FROM edges e LEFT JOIN nodes n ON n.id = e.target_id "
        "WHERE e.edge_type IN ('depends_on', 'realizes', 'uses_var') "
        "AND (n.id IS NULL OR n.status = 'deprecated') "
        "ORDER BY 1, 3, 2"
    )
    for source, target, edge_type, missing in rows:
        doc = ctx.by_id[source]
        state = "does not exist" if missing else "is deprecated"
        out.append(_fail("R-LINT-003", _rel(doc), _field_line(ctx.lines(doc), edge_type),
                         f"{edge_type} references '{target}', which {state}"))
    for doc in ctx.of_type("architecture"):
        for target in _as_list(ctx.fm(doc).get("depends_on")):
            ref = ctx.by_id.get(target)
            if ref is None or ctx.fm(ref).get("status") == "deprecated":
                state = "does not exist" if ref is None else "is deprecated"
                out.append(_fail("R-LINT-003", _rel(doc),
                                 _field_line(ctx.lines(doc), "depends_on"),
                                 f"depends_on references '{target}', which {state}"))
    return out


def _native_cycles(adj):
    reach = {}
    for start in adj:
        seen = set()
        stack = list(adj[start])
        while stack:
            node = stack.pop()
            if node not in seen:
                seen.add(node)
                stack.extend(adj.get(node, ()))
        reach[start] = seen
    return sorted({
        tuple(sorted(m for m in reach[a] if a in reach.get(m, ())))
        for a in adj
        if a in reach[a]
    })


def _r004(ctx):
    out = []
    rows = ctx.query(
        "WITH RECURSIVE dep AS ("
        " SELECT DISTINCT source_id AS src, target_id AS dst FROM edges"
        " WHERE edge_type = 'depends_on'"
        "), reach(src, dst) AS ("
        " SELECT src, dst FROM dep"
        " UNION"
        " SELECT reach.src, dep.dst FROM reach JOIN dep ON dep.src = reach.dst"
        ") "
        "SELECT DISTINCT a.src, a.dst FROM reach a "
        "JOIN reach b ON a.src = b.dst AND a.dst = b.src "
        "ORDER BY 1, 2"
    )
    groups = {}
    for src, dst in rows:
        groups.setdefault(src, set()).add(dst)
    cycles = sorted({tuple(sorted(members)) for members in groups.values()})
    adj = {
        _get(doc, "doc_id"): _as_list(ctx.fm(doc).get("depends_on"))
        for doc in ctx.of_type("architecture")
    }
    for cycle in cycles + _native_cycles(adj):
        doc = ctx.by_id[cycle[0]]
        out.append(_fail("R-LINT-004", _rel(doc), _field_line(ctx.lines(doc), "depends_on"),
                         f"depends_on cycle among {', '.join(cycle)}"))
    return out


def _r005(ctx):
    out = []
    for doc in ctx.of_type("component-root"):
        fm = ctx.fm(doc)
        lines = ctx.lines(doc)
        if fm.get("sealed") is True and not fm.get("source_path"):
            out.append(_fail("R-LINT-005", _rel(doc), _field_line(lines, "sealed"),
                             "sealed: true requires a source_path"))
        if fm.get("source_path") and fm.get("sealed") is not True:
            out.append(_fail("R-LINT-005", _rel(doc), _field_line(lines, "source_path"),
                             "source_path is set but sealed is false or absent"))
    return out


def _r006(ctx):
    out = []
    for doc in ctx.of_type("component-root"):
        fm = ctx.fm(doc)
        if fm.get("sealed") is not True and not _as_list(fm.get("realizes")):
            out.append(_fail("R-LINT-006", _rel(doc),
                             _field_line(ctx.lines(doc), "realizes"),
                             "non-sealed component has zero realizes entries"))
    return out


def _unit_ids(ctx, rule_id, doc_type, prefix, label):
    pattern = re.compile(prefix + r"-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}")
    out = []
    seen = {}
    for doc in ctx.of_type(doc_type):
        rel = _rel(doc)
        stem = Path(rel).stem
        text = ctx.text(doc)
        lines = text.splitlines()
        if not pattern.fullmatch(stem):
            out.append(_fail(rule_id, rel, 1,
                             f"{label} id '{stem}' does not match {prefix}-<comp>-NNN"))
        if stem in seen:
            out.append(_fail(rule_id, rel, 1,
                             f"{label} id '{stem}' duplicates {seen[stem]}"))
        seen.setdefault(stem, rel)
        number, heading = next(
            ((i + 1, l[2:].strip()) for i, l in enumerate(lines) if l.startswith("# ")),
            (1, ""),
        )
        if heading != stem:
            out.append(_fail(rule_id, rel, number,
                             f"heading '# {heading}' does not match filename '{stem}'"))
        if not _RFC2119.search(text):
            out.append(_fail(rule_id, rel, 1, f"{label} {stem} uses no RFC 2119 keyword"))
    return out


def _r007(ctx):
    return _unit_ids(ctx, "R-LINT-007", "component-requirement", "R", "requirement")


def _r008(ctx):
    rows = ctx.query(
        "SELECT n.id, n.owner_component_id FROM nodes n "
        "WHERE n.kind = 'requirement' AND NOT EXISTS ("
        " SELECT 1 FROM edges e WHERE e.edge_type = 'covers' AND e.target_id = n.id) "
        "ORDER BY 2, 1"
    )
    return [
        _fail("R-LINT-008",
              f"specs/components/{owner.removeprefix('comp-')}/requirements/{rid}.md", 1,
              f"requirement {rid} has no covering acceptance criterion")
        for rid, owner in rows
    ]


def _criterion_locations(ctx):
    locs = {}
    for doc in ctx.of_type("component-acceptance"):
        lines = ctx.lines(doc)
        number = next((i + 1 for i, l in enumerate(lines) if "Covers:" in l), 1)
        locs[_get(doc, "doc_id")] = (_rel(doc), number)
    for doc in ctx.of_type("product"):
        lines = ctx.lines(doc)
        for i, line in enumerate(lines):
            match = _CS_HEADING.match(line)
            if match:
                number = next(
                    (j + 1 for j in range(i + 1, len(lines)) if "Covers:" in lines[j]),
                    i + 1,
                )
                locs[match.group(1)] = (_rel(doc), number)
    return locs


def _r009(ctx):
    rows = ctx.query(
        "SELECT DISTINCT e.source_id, e.target_id FROM edges e "
        "WHERE e.edge_type = 'covers' AND NOT EXISTS ("
        " SELECT 1 FROM nodes n WHERE n.id = e.target_id"
        " AND n.kind IN ('requirement', 'capability')) "
        "ORDER BY 1, 2"
    )
    locs = _criterion_locations(ctx)
    out = []
    for source, target in rows:
        rel, number = locs.get(source, ("", 1))
        message = _COVERS_MSG.get(target[:2], _COVERS_NEITHER).format(target)
        out.append(_fail("R-LINT-009", rel, number, message))
    return out


def _r010(ctx):
    out = []
    for doc in ctx.of_type("component-acceptance"):
        text = ctx.text(doc)
        lines = text.splitlines()
        start = next((i for i, l in enumerate(lines) if "Covers:" in l), -1) + 1
        if not any(_KIND.match(l) for l in lines[start:]):
            out.append(_fail("R-LINT-010", _rel(doc), 1,
                             "acceptance criterion is missing a Kind"))
        missing = [w for w in ("Given", "When", "Then")
                   if not re.search(rf"^\W*{w}\b", text, re.MULTILINE)]
        if missing:
            out.append(_fail("R-LINT-010", _rel(doc), 1,
                             "incomplete Given/When/Then block: missing "
                             + ", ".join(missing)))
    return out


def _definition_entries(ctx):
    found = []
    for doc in ctx.of_type("component-root"):
        _, body = _section(ctx.lines(doc), "Definitions")
        entries = []
        for number, text in body:
            match = _ENTRY.match(text)
            if match:
                entries.append([number, match.group(1).strip(), [match.group(2)]])
            elif entries:
                entries[-1][2].append(text)
        for number, term, parts in entries:
            gloss = ctx.glossary_defs.get(term.lower())
            if gloss is not None:
                local = _LEAD.sub("", "\n".join(parts)).strip()
                found.append((doc, number, term, local, gloss, _overlap(local, gloss)))
    return found


def _r011(ctx):
    return [
        _fail("R-LINT-011", _rel(doc), number,
              f"Definitions entry for '{term}' restates the glossary definition "
              f"(token overlap {ratio:.2f}); only deltas belong here")
        for doc, number, term, _local, _gloss, ratio in _definition_entries(ctx)
        if ratio >= 0.8
    ]


def _r013(ctx):
    out = []
    for doc in ctx.of_type("var"):
        bullets = []
        for i, line in enumerate(ctx.lines(doc)):
            match = _BULLET.match(line)
            if match:
                word = _WORD.search(match.group(2))
                bullets.append((i + 1, match.group(1).lower(), word and word.group(0).lower()))
        if any(name == "sensitivity" and value == "secret" for _, name, value in bullets):
            for number, name, _value in bullets:
                if name in ("example", "default"):
                    out.append(_fail("R-LINT-013", _rel(doc), number,
                                     f"secret var declaration carries a '{name}' field"))
    return out


def _r014(ctx):
    rels = sorted(_relpath(p, ctx.repo_root) for p in ctx.glossary_files)
    if len(rels) < 2:
        return []
    if any(_BOUNDED.search(ctx.text(doc)) for doc in ctx.of_type("architecture")):
        return []
    return [
        _fail("R-LINT-014", rel, 1,
              f"multiple glossary files ({', '.join(rels)}) without an "
              "architecture-level bounded-context split decision")
        for rel in rels
        if rel != "specs/glossary.md"
    ]


def _r015(ctx):
    out = []
    for doc, number, term, local, gloss, ratio in _definition_entries(ctx):
        if ratio >= 0.8:
            continue
        if ctx.judge is None:
            out.append(_fail("R-LINT-015", _rel(doc), number,
                             f"skipped: no model configured to judge the Definitions "
                             f"entry for '{term}'", severity="skipped"))
            continue
        verdict = ctx.judge(term, local, gloss)
        if verdict is None:
            out.append(_fail("R-LINT-015", _rel(doc), number,
                             f"skipped: the judge could not evaluate the Definitions "
                             f"entry for '{term}'", severity="skipped"))
            continue
        conflicts, rationale = verdict
        if conflicts:
            out.append(_fail("R-LINT-015", _rel(doc), number,
                             f"Definitions entry for '{term}' conflicts with the "
                             "glossary definition", rationale=rationale))
    return out


def _r016(ctx):
    return [
        _fail("R-LINT-016", _rel(doc), 1,
              "unit file carries a YAML frontmatter block; frontmatter belongs only "
              "on component.md")
        for doc in ctx.of_type(*_UNIT_TYPES)
        if _get(doc, "has_frontmatter", False)
    ]


def _r017(ctx):
    return _unit_ids(ctx, "R-LINT-017", "component-interface-guarantee", "G", "guarantee")


def _r018(ctx):
    out = []
    unresolved = ctx.query(
        "SELECT DISTINCT e.source_id, e.target_id FROM edges e "
        "WHERE e.edge_type = 'depends_on_guarantees' AND NOT EXISTS ("
        " SELECT 1 FROM nodes n WHERE n.id = e.target_id AND n.kind = 'guarantee') "
        "ORDER BY 1, 2"
    )
    for source, target in unresolved:
        doc = ctx.by_id[source]
        out.append(_fail("R-LINT-018", _rel(doc),
                         _field_line(ctx.lines(doc), "depends_on_guarantees"),
                         f"depends_on_guarantees references '{target}', which is not "
                         "an existing guarantee id"))
    undeclared = ctx.query(
        "SELECT DISTINCT e.source_id, e.target_id, n.owner_component_id FROM edges e "
        "JOIN nodes n ON n.id = e.target_id AND n.kind = 'guarantee' "
        "WHERE e.edge_type = 'depends_on_guarantees' AND NOT EXISTS ("
        " SELECT 1 FROM edges d WHERE d.edge_type = 'depends_on'"
        " AND d.source_id = e.source_id AND d.target_id = n.owner_component_id) "
        "ORDER BY 1, 2"
    )
    for source, target, owner in undeclared:
        doc = ctx.by_id[source]
        out.append(_fail("R-LINT-018", _rel(doc),
                         _field_line(ctx.lines(doc), "depends_on_guarantees"),
                         f"depends_on_guarantees entry '{target}' belongs to {owner}, "
                         "which is not listed in depends_on"))
    return out


def _r019(ctx):
    targets = [(_rel(doc), ctx.text(doc)) for doc in ctx.docs]
    targets += [
        (_relpath(p, ctx.repo_root), Path(p).read_text(encoding="utf-8"))
        for p in ctx.glossary_files
    ]
    return [
        _fail("R-LINT-019", rel, number, "line ends in trailing whitespace")
        for rel, text in targets
        for number, line in enumerate(text.splitlines(), start=1)
        if line != line.rstrip()
    ]


def _r024(ctx):
    out = []
    for doc in ctx.of_type("component-root"):
        _, body = _section(ctx.lines(doc), "Purpose")
        for number, text in body:
            for match in _DECISION.finditer(text):
                out.append(_fail("R-LINT-024", _rel(doc), number,
                                 f"Purpose cites decision {match.group(0)}; decision "
                                 "citations belong in Rationale"))
    return out


def _r031(ctx):
    covered = {row[0] for row in ctx.query(
        "SELECT DISTINCT target_id FROM edges WHERE edge_type = 'covers'")}
    out = []
    for name in sorted(ctx.components):
        component = ctx.components[name]
        cli = _get(component, "interface_cli")
        if cli is None:
            continue
        requirements = _get(component, "requirements", {})
        if not any(rid in covered and "interface/cli.md" in ctx.text(doc)
                   for rid, doc in requirements.items()):
            out.append(_fail("R-LINT-031", _rel(cli), 1,
                             f"comp-{name} has interface/cli.md but no requirement that "
                             "cites interface/cli.md and is covered by a criterion "
                             "(SPEC_GUIDELINES.md §5)", severity="warn"))
    return out


def _r032(ctx):
    if not (ctx.repo_root / ".hotdocs-tool.json").exists():
        return []
    gen = _tool_root() / "gen"
    return [
        _fail("R-LINT-032", f"specs/components/{name}/component.md", 1,
              f"component '{name}' would shadow the tool's own gen/{name}/")
        for name in sorted(ctx.components)
        if (gen / name).is_dir()
    ]


_RULES = (
    _r001, _r002, _r003, _r004, _r005, _r006, _r007, _r008, _r009, _r010,
    _r011, _r013, _r014, _r015, _r016, _r017, _r018, _r019, _r024, _r031, _r032,
)


# --------------------------------------------------------------------------
# Library entry point
# --------------------------------------------------------------------------


def _select(findings, paths, repo_root):
    if paths is None:
        return findings
    prefixes = [
        _relpath(Path(p) if Path(p).is_absolute() else repo_root / p, repo_root)
        for p in paths
    ]
    return [
        f for f in findings
        if any(f.file == p or f.file.startswith(p + "/") for p in prefixes)
    ]


def lint(paths, repo_root, strict=False, judge=None):
    """Lint the spec corpus under ``repo_root``; ``paths=None`` lints all of it."""
    repo_root = Path(repo_root)
    loader = _load_dep(repo_root, "corpus-loader", "corpus_loader")
    ctx = _Ctx(loader.load_corpus(repo_root), repo_root, judge)
    findings = []
    for rule in _RULES:
        findings.extend(rule(ctx))
    for slug, module_name in (("citation-checker", "citation_checker"),
                              ("size-checker", "size_checker")):
        checker = _load_dep(repo_root, slug, module_name)
        for item in checker.check(repo_root):
            findings.append(Finding(
                _get(item, "rule_id"),
                _get(item, "severity"),
                _get(item, "file"),
                _get(item, "line"),
                _get(item, "message"),
            ))
    return LintReport(_select(findings, paths, repo_root), strict)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _git_root():
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise _UsageError("not inside a git repository; pass --repo-root")
    return Path(proc.stdout.strip())


def _parse(argv):
    values = {"--format": "text", "--repo-root": None}
    strict = False
    paths = []
    i = 0
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in values:
            if not eq:
                if i + 1 == len(argv):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                value = argv[i]
            values[name] = value
        elif token == "--strict":
            strict = True
        elif token.startswith("-"):
            raise _UsageError(f"unknown argument '{token}'")
        else:
            paths.append(Path(token))
        i += 1
    if values["--format"] not in ("json", "text"):
        raise _UsageError(f"--format must be json or text, not '{values['--format']}'")
    repo = values["--repo-root"]
    repo_root = Path(repo) if repo is not None else _git_root()
    if not repo_root.is_dir():
        raise _UsageError(f"repository root '{repo_root}' is not a directory")
    for path in paths:
        if not (path if path.is_absolute() else repo_root / path).exists():
            raise _UsageError(f"path '{path}' does not exist")
    return values["--format"], repo_root, strict, paths or None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        fmt, repo_root, strict, paths = _parse(argv)
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    report = lint(paths, repo_root, strict=strict)
    if fmt == "json":
        print(json.dumps(report.to_json(), indent=2))
    else:
        for f in report.findings:
            print(f"{f.file}:{f.line}: {f.severity} {f.rule_id}: {f.message}")
        print(f"{report.hard_failures} hard failure(s), {report.warnings} warning(s), "
              f"{report.skipped} skipped")
    return 1 if report.hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())
