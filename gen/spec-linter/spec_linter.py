"""spec-linter: mechanically validates a spec corpus against SPEC_GUIDELINES.md.

Library: ``lint(paths, repo_root, strict=False, judge=None) -> LintReport`` and
``load_corpus`` (corpus-loader's own function, re-exported).
CLI: ``main(argv) -> int`` (``hotdocs lint``; ``python -m spec_linter``).
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

FRONTMATTER_TYPES = ("component-root", "product", "architecture", "var", "decision")
UNIT_TYPES = (
    "component-requirement",
    "component-interface-cli",
    "component-interface-library",
    "component-interface-data",
    "component-interface-guarantee",
    "component-acceptance",
    "component-constraints",
)
REQUIRED_FIELDS = ("id", "title", "status", "owners")
LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "builds_on")
STATUSES = ("draft", "ratified", "deprecated")
KINDS = ("compiled", "generated-test", "llm-judge")
RFC2119 = re.compile(r"\b(MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)\b")
DECISION_ID = re.compile(r"\bD\d+\b")
ASSET_SECTIONS = (
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
)
USAGE = "usage: hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]"


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
    rationale: object = None

    def to_json(self) -> dict:
        out = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }
        if self.rationale is not None:
            out["rationale"] = self.rationale
        return out


@dataclass
class LintReport:
    findings: list = field(default_factory=list)
    strict: bool = False

    def _count(self, *severities) -> int:
        return sum(1 for f in self.findings if f.severity in severities)

    @property
    def hard_failures(self) -> int:
        if self.strict:
            return self._count("fail", "warn")
        return self._count("fail")

    @property
    def warnings(self) -> int:
        return self._count("warn")

    @property
    def skipped(self) -> int:
        return self._count("skipped")

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


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_dependency(repo_root, slug: str):
    name = slug.replace("-", "_")
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    package = base / name / "__init__.py"
    if package.is_file():
        spec = importlib.util.spec_from_file_location(
            name, package, submodule_search_locations=[str(package.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location(name, base / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def __getattr__(name):
    if name == "load_corpus":
        fn = _load_dependency(_tool_root(), "corpus-loader").load_corpus
        globals()["load_corpus"] = fn
        return fn
    raise AttributeError(name)


def _g(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


# --------------------------------------------------------------------------
# Corpus view
# --------------------------------------------------------------------------


@dataclass
class _Doc:
    path: Path
    rel: str
    id: object
    fm: dict
    body: str
    type: str
    has_fm: bool
    lines: list

    @property
    def slug(self) -> str:
        return self.rel.split("/")[2]


class _Ctx:
    def __init__(self, corpus, repo_root: Path, judge):
        self.repo_root = repo_root
        self.tool_root = _tool_root()
        self.judge = judge
        self.graph = _g(corpus, "graph")
        docs = []
        for d in _g(corpus, "docs"):
            path = Path(_g(d, "path"))
            docs.append(
                _Doc(
                    path=path,
                    rel=_g(d, "rel_path"),
                    id=_g(d, "doc_id"),
                    fm=dict(_g(d, "frontmatter") or {}),
                    body=_g(d, "body") or "",
                    type=_g(d, "doc_type"),
                    has_fm=bool(_g(d, "has_frontmatter")),
                    lines=path.read_text(encoding="utf-8").splitlines(),
                )
            )
        self.docs = sorted(docs, key=lambda d: d.rel)
        self.glossary_defs = dict(_g(corpus, "glossary_defs") or {})
        self.glossary_files = sorted(Path(p) for p in (_g(corpus, "glossary_files") or []))
        self.components = sorted(_g(corpus, "components") or {})
        self.fm_docs = [d for d in self.docs if d.type in FRONTMATTER_TYPES]
        self.roots = self.of("component-root")
        self.arch = self.of("architecture")
        self.root_by_id = {d.fm.get("id"): d for d in self.roots}
        self.id_docs = {d.id: d for d in self.fm_docs}

    def of(self, doc_type: str) -> list:
        return [d for d in self.docs if d.type == doc_type]

    def q(self, sql: str) -> list:
        return self.graph.execute(sql).fetchall()

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.repo_root.resolve()).as_posix()


def _fail(rule, file, line, message, rationale=None):
    return Finding(rule, "fail", file, line, message, rationale)


def _key_line(d: _Doc, key: str) -> int:
    return next((i + 1 for i, l in enumerate(d.lines) if l.startswith(f"{key}:")), 1)


def _entries(value) -> list:
    if isinstance(value, list):
        return value
    return [value] if value else []


def _section(lines: list, name: str):
    """(heading index, content lines) of the `## name` section, or (None, [])."""
    for i, line in enumerate(lines):
        if line.strip() == f"## {name}":
            end = next(
                (j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")),
                len(lines),
            )
            return i, lines[i + 1 : end]
    return None, []


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------


def _r001(c: _Ctx) -> list:
    out = []
    for d in c.fm_docs:
        for name in REQUIRED_FIELDS:
            if name not in d.fm:
                out.append(_fail("R-LINT-001", d.rel, 1, f"frontmatter lacks required field '{name}'"))
        for name in LIST_FIELDS:
            if name in d.fm and not isinstance(d.fm[name], list):
                out.append(_fail("R-LINT-001", d.rel, _key_line(d, name), f"'{name}' must be a list"))
        if "sealed" in d.fm and not isinstance(d.fm["sealed"], bool):
            out.append(_fail("R-LINT-001", d.rel, _key_line(d, "sealed"), "'sealed' must be a boolean"))
        if "status" in d.fm and d.fm["status"] not in STATUSES:
            out.append(
                _fail(
                    "R-LINT-001",
                    d.rel,
                    _key_line(d, "status"),
                    f"status must be draft, ratified or deprecated, not '{d.fm['status']}'",
                )
            )
    return out


def _r002(c: _Ctx) -> list:
    out = []
    for d in c.fm_docs:
        if d.fm.get("status") != "ratified":
            continue
        i, body = _section(d.lines, "Open questions")
        if "".join(body).strip():
            out.append(_fail("R-LINT-002", d.rel, i + 1, "ratified spec has a non-empty Open questions section"))
        if not d.fm.get("last_ratified_commit"):
            out.append(_fail("R-LINT-002", d.rel, _key_line(d, "status"), "ratified spec lacks last_ratified_commit"))
    return out


_SQL_003 = """
SELECT DISTINCT e.source_id, e.edge_type, e.target_id, n.id IS NULL AS missing
FROM edges e
JOIN nodes s ON s.id = e.source_id AND s.kind = 'component'
LEFT JOIN nodes n ON n.id = e.target_id
WHERE e.edge_type IN ('depends_on', 'realizes', 'uses_var')
  AND (n.id IS NULL OR n.status = 'deprecated')
ORDER BY e.source_id, e.edge_type, e.target_id
"""


def _r003(c: _Ctx) -> list:
    out = []
    for src, etype, target, missing in c.q(_SQL_003):
        d = c.root_by_id[src]
        state = "does not exist" if missing else "is deprecated"
        out.append(_fail("R-LINT-003", d.rel, _key_line(d, etype), f"{etype} references '{target}', which {state}"))
    # Native residual (D13): architecture docs' own depends_on.
    for d in c.arch:
        for target in _entries(d.fm.get("depends_on")):
            ref = c.id_docs.get(target)
            if ref is None:
                state = "does not exist"
            elif ref.fm.get("status") == "deprecated":
                state = "is deprecated"
            else:
                continue
            out.append(
                _fail("R-LINT-003", d.rel, _key_line(d, "depends_on"), f"depends_on references '{target}', which {state}")
            )
    return out


_SQL_004 = """
WITH RECURSIVE dep AS (
  SELECT DISTINCT e.source_id AS src, e.target_id AS dst
  FROM edges e
  JOIN nodes s ON s.id = e.source_id AND s.kind = 'component'
  WHERE e.edge_type = 'depends_on'
),
walk(start_id, cur, path) AS (
  SELECT src, dst, [src, dst] FROM dep WHERE dst >= src
  UNION ALL
  SELECT w.start_id, d.dst, list_append(w.path, d.dst)
  FROM walk w JOIN dep d ON d.src = w.cur
  WHERE w.cur <> w.start_id
    AND d.dst >= w.start_id
    AND (d.dst = w.start_id OR NOT list_contains(w.path, d.dst))
)
SELECT start_id, path FROM walk WHERE cur = start_id ORDER BY start_id, path
"""


def _r004(c: _Ctx) -> list:
    out = []
    for start, path in c.q(_SQL_004):
        d = c.root_by_id[start]
        out.append(
            _fail("R-LINT-004", d.rel, _key_line(d, "depends_on"), f"depends_on cycle: {' -> '.join(path)}")
        )
    # Native residual (D13): cycles among architecture docs' depends_on.
    arch = {d.id: d for d in c.arch}
    graph = {i: [t for t in _entries(d.fm.get("depends_on")) if t in arch] for i, d in arch.items()}
    cycles = []

    def walk(start, node, path):
        for target in graph[node]:
            if target == start:
                cycles.append(path + [start])
            elif target not in path and target > start:
                walk(start, target, path + [target])

    for start in sorted(graph):
        walk(start, start, [start])
    for path in cycles:
        d = arch[path[0]]
        out.append(
            _fail("R-LINT-004", d.rel, _key_line(d, "depends_on"), f"depends_on cycle: {' -> '.join(path)}")
        )
    return out


def _r005(c: _Ctx) -> list:
    out = []
    for d in c.roots:
        sealed = d.fm.get("sealed") is True
        if sealed and not d.fm.get("source_path"):
            out.append(_fail("R-LINT-005", d.rel, _key_line(d, "sealed"), "sealed: true requires a source_path"))
        if d.fm.get("source_path") and not sealed:
            out.append(
                _fail("R-LINT-005", d.rel, _key_line(d, "source_path"), "source_path is set but sealed is not true")
            )
    return out


def _r006(c: _Ctx) -> list:
    return [
        _fail("R-LINT-006", d.rel, _key_line(d, "realizes"), "non-sealed component has no realizes entries")
        for d in c.roots
        if d.fm.get("sealed") is not True and not _entries(d.fm.get("realizes"))
    ]


def _unit_ids(c: _Ctx, doc_type: str, rule: str, prefix: str, noun: str) -> list:
    out = []
    pattern = re.compile(rf"{prefix}-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{{3}}")
    seen = {}
    for d in c.of(doc_type):
        stem = d.path.stem
        if not pattern.fullmatch(stem):
            out.append(_fail(rule, d.rel, 1, f"{noun} filename '{stem}' is not a {prefix}-<comp>-NNN id"))
        if stem in seen:
            out.append(_fail(rule, d.rel, 1, f"{noun} id '{stem}' is not unique (also {seen[stem]})"))
        seen.setdefault(stem, d.rel)
        idx = next((i for i, l in enumerate(d.lines) if l.startswith("# ")), 0)
        heading = d.lines[idx] if d.lines else ""
        if heading.strip() != f"# {stem}":
            out.append(_fail(rule, d.rel, idx + 1, f"heading '# {stem}' missing or not equal to the filename"))
        if not RFC2119.search(d.body):
            out.append(_fail(rule, d.rel, 1, f"{noun} {stem} uses no RFC 2119 keyword"))
    return out


def _r007(c: _Ctx) -> list:
    return _unit_ids(c, "component-requirement", "R-LINT-007", "R", "requirement")


_SQL_008 = """
SELECT DISTINCT n.id FROM nodes n
WHERE n.kind = 'requirement'
  AND NOT EXISTS (
    SELECT 1 FROM edges e WHERE e.edge_type = 'covers' AND e.target_id = n.id
  )
ORDER BY n.id
"""


def _r008(c: _Ctx) -> list:
    reqs = {}
    for d in c.of("component-requirement"):
        reqs.setdefault(d.id, d)
    return [
        _fail("R-LINT-008", reqs[rid].rel, 1, f"{rid} has no covering acceptance criterion")
        for (rid,) in c.q(_SQL_008)
    ]


_SQL_009 = """
SELECT DISTINCT e.source_id, e.target_id FROM edges e
WHERE e.edge_type = 'covers'
  AND NOT EXISTS (
    SELECT 1 FROM nodes n
    WHERE n.id = e.target_id AND n.kind IN ('requirement', 'capability')
  )
ORDER BY 1, 2
"""


def _covers_locations(c: _Ctx) -> dict:
    """Native scan (R-LINT-021's exception): criterion id -> (file, line)."""
    loc = {}
    for d in c.of("component-acceptance"):
        loc[d.id] = (d.rel, next((i + 1 for i, l in enumerate(d.lines) if "Covers:" in l), 1))
    for d in c.of("product"):
        for i, line in enumerate(d.lines):
            m = re.match(r"###\s+(CS-[A-Za-z0-9-]+)", line)
            if m:
                at = next((j for j in range(i + 1, len(d.lines)) if "Covers:" in d.lines[j]), i)
                loc[m.group(1)] = (d.rel, at + 1)
    return loc


def _r009(c: _Ctx) -> list:
    out = []
    loc = _covers_locations(c)
    for src, target in c.q(_SQL_009):
        file, line = loc[src]
        if target.startswith("R-"):
            msg = f"Covers: '{target}' does not resolve to a real requirement"
        elif target.startswith("P-"):
            msg = f"Covers: '{target}' does not resolve to a real capability"
        else:
            msg = f"Covers: '{target}' is neither an R-id nor a P-id"
        out.append(_fail("R-LINT-009", file, line, msg))
    return out


def _r010(c: _Ctx) -> list:
    out = []
    for d in c.of("component-acceptance"):
        tag = next((i for i, l in enumerate(d.lines) if "Covers:" in l), 0)
        kinds = [l.strip() for l in d.lines[tag:]]
        if not any(k in (f"Kind: {kind}" for kind in KINDS) for k in kinds):
            out.append(
                _fail("R-LINT-010", d.rel, 1, f"{d.id} has no Kind: line (compiled, generated-test or llm-judge)")
            )
        if not all(re.search(rf"^\s*{w}\b", d.body, re.M) for w in ("Given", "When", "Then")):
            out.append(_fail("R-LINT-010", d.rel, 1, f"{d.id} has no complete Given/When/Then block"))
    return out


def _definition_entries(root: _Doc) -> list:
    i, body = _section(root.lines, "Definitions")
    entries = []
    for j, line in enumerate(body):
        m = re.match(r"- \*\*(.+?)\*\*(.*)", line)
        if m:
            entries.append([m.group(1), i + j + 2, [m.group(2)]])
        elif entries:
            entries[-1][2].append(line)
    return [(term, line, re.sub(r"^[\s—-]+", "", "\n".join(parts)).strip()) for term, line, parts in entries]


def _tokens(text: str) -> set:
    return set(re.findall(r"\w+", text.lower()))


def _glossary_entries(c: _Ctx) -> list:
    """(root, term, line, local_text, glossary_text, near_verbatim) per entry naming a term."""
    out = []
    for d in c.roots:
        for term, line, local in _definition_entries(d):
            gloss = c.glossary_defs.get(term.lower())
            if gloss is None:
                continue
            g = _tokens(gloss)
            ratio = len(_tokens(local) & g) / max(len(g), 1)
            out.append((d, term, line, local, gloss, ratio >= 0.8))
    return out


def _r011(c: _Ctx) -> list:
    return [
        _fail("R-LINT-011", d.rel, line, f"Definitions entry '{term}' restates the glossary's definition; only deltas belong here")
        for d, term, line, _local, _gloss, near in _glossary_entries(c)
        if near
    ]


def _r013(c: _Ctx) -> list:
    out = []
    for d in c.of("var"):
        fields = {}
        for n, line in enumerate(d.lines, 1):
            m = re.match(r"\s*[-*]\s+(.*)", line)
            if m:
                key, sep, value = m.group(1).replace("*", "").replace("`", "").partition(":")
                if sep:
                    fields.setdefault(key.strip().lower(), (value.strip(), n))
        if re.match(r"secret(?![\w-])", fields.get("sensitivity", ("", 0))[0]):
            for name in ("example", "default"):
                if name in fields:
                    out.append(
                        _fail(
                            "R-LINT-013",
                            d.rel,
                            fields[name][1],
                            f"secret var declares '{name}'; a secret never carries an example or default",
                        )
                    )
    return out


def _r014(c: _Ctx) -> list:
    if len(c.glossary_files) < 2:
        return []
    if any(re.search(r"bounded[- ]context", d.body, re.I) for d in c.arch):
        return []
    rels = [c.rel(p) for p in c.glossary_files]
    return [
        _fail(
            "R-LINT-014",
            rel,
            1,
            f"glossary-like file {rel} exists alongside {', '.join(r for r in rels if r != rel)} "
            "without an architecture/-level bounded-context split decision",
        )
        for rel in rels
        if rel != "specs/glossary.md"
    ]


def _r015(c: _Ctx) -> list:
    out = []
    for d, term, line, local, gloss, near in _glossary_entries(c):
        if near:
            continue
        if c.judge is None:
            out.append(
                Finding(
                    "R-LINT-015",
                    "skipped",
                    d.rel,
                    line,
                    f"Definitions entry '{term}' not judged: no model configured (R-LINT-015 skipped)",
                )
            )
            continue
        verdict = c.judge(term, local, gloss)
        if verdict is None:
            out.append(Finding("R-LINT-015", "skipped", d.rel, line, f"Definitions entry '{term}' could not be judged"))
            continue
        conflicts, rationale = verdict
        if conflicts:
            out.append(
                _fail("R-LINT-015", d.rel, line, f"Definitions entry '{term}' conflicts with the glossary's definition", rationale)
            )
    return out


def _r016(c: _Ctx) -> list:
    return [
        _fail("R-LINT-016", d.rel, 1, "unit file carries a frontmatter block; frontmatter lives only on component.md")
        for d in c.docs
        if d.type in UNIT_TYPES and d.has_fm
    ]


def _r017(c: _Ctx) -> list:
    return _unit_ids(c, "component-interface-guarantee", "R-LINT-017", "G", "guarantee")


_SQL_018_MISSING = """
SELECT DISTINCT e.source_id, e.target_id FROM edges e
WHERE e.edge_type = 'depends_on_guarantees'
  AND NOT EXISTS (SELECT 1 FROM nodes n WHERE n.id = e.target_id AND n.kind = 'guarantee')
ORDER BY 1, 2
"""

_SQL_018_OWNER = """
SELECT DISTINCT e.source_id, e.target_id, n.owner_component_id FROM edges e
JOIN nodes n ON n.id = e.target_id AND n.kind = 'guarantee'
WHERE e.edge_type = 'depends_on_guarantees'
  AND NOT EXISTS (
    SELECT 1 FROM edges d
    WHERE d.edge_type = 'depends_on'
      AND d.source_id = e.source_id
      AND d.target_id = n.owner_component_id
  )
ORDER BY 1, 2
"""


def _r018(c: _Ctx) -> list:
    out = []
    for src, target in c.q(_SQL_018_MISSING):
        d = c.root_by_id[src]
        out.append(
            _fail(
                "R-LINT-018",
                d.rel,
                _key_line(d, "depends_on_guarantees"),
                f"depends_on_guarantees references '{target}', which does not exist",
            )
        )
    for src, target, owner in c.q(_SQL_018_OWNER):
        d = c.root_by_id[src]
        out.append(
            _fail(
                "R-LINT-018",
                d.rel,
                _key_line(d, "depends_on_guarantees"),
                f"depends_on_guarantees references '{target}', owned by '{owner}', which depends_on does not list",
            )
        )
    return out


def _r019(c: _Ctx) -> list:
    files = [(d.rel, d.lines) for d in c.docs]
    files += [(c.rel(p), p.read_text(encoding="utf-8").splitlines()) for p in c.glossary_files]
    return [
        _fail("R-LINT-019", rel, n, "line ends in trailing whitespace")
        for rel, lines in sorted(files)
        for n, line in enumerate(lines, 1)
        if line != line.rstrip()
    ]


def _r024(c: _Ctx) -> list:
    out = []
    for d in c.roots:
        i, body = _section(d.lines, "Purpose")
        for j, line in enumerate(body):
            for m in DECISION_ID.finditer(line):
                out.append(
                    _fail(
                        "R-LINT-024",
                        d.rel,
                        i + j + 2,
                        f"Purpose cites decision {m.group(0)}; decision citations belong in Rationale",
                    )
                )
    return out


def _r031(c: _Ctx) -> list:
    out = []
    covered = {t for (t,) in c.q("SELECT DISTINCT target_id FROM edges WHERE edge_type = 'covers'")}
    reqs = c.of("component-requirement")
    for cli in c.of("component-interface-cli"):
        if not cli.rel.endswith("/interface/cli.md"):
            continue
        citing = [r for r in reqs if r.slug == cli.slug and "interface/cli.md" in r.body]
        if not any(r.id in covered for r in citing):
            out.append(
                Finding(
                    "R-LINT-031",
                    "warn",
                    cli.rel,
                    1,
                    f"comp-{cli.slug} has interface/cli.md but no requirement citing interface/cli.md "
                    "that a criterion covers (see SPEC_GUIDELINES.md §5)",
                )
            )
    return out


def _r032(c: _Ctx) -> list:
    if not (c.repo_root / ".hotdocs-tool.json").exists():
        return []
    return [
        _fail(
            "R-LINT-032",
            f"specs/components/{slug}/component.md",
            1,
            f"component '{slug}' would shadow the tool's own gen/{slug}/",
        )
        for slug in c.components
        if (c.tool_root / "gen" / slug).is_dir()
    ]


def _asset_kind_findings(c: _Ctx, d: _Doc, line: int, kind: str) -> list:
    definition = c.repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"
    adapter = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    if not definition.is_file() and not (c.repo_root / adapter).is_file() and not (c.tool_root / adapter).is_file():
        return [_fail("R-LINT-034", d.rel, line, f"asset kind '{kind}' has no definition; run hotdocs kind new {kind}")]
    if not definition.is_file():
        return []
    out = []
    lines = definition.read_text(encoding="utf-8").splitlines()
    for name in ASSET_SECTIONS:
        i, body = _section(lines, name)
        if i is None:
            out.append(_fail("R-LINT-034", d.rel, line, f"asset kind '{kind}' definition lacks section '{name}'"))
        elif not "".join(body).strip():
            out.append(_fail("R-LINT-034", d.rel, line, f"asset kind '{kind}' definition has empty section '{name}'"))
    if f"comp-kind-{kind}" not in _entries(d.fm.get("depends_on")):
        out.append(
            _fail(
                "R-LINT-034",
                d.rel,
                line,
                f"asset kind '{kind}' is defined in this repository; depends_on must list comp-kind-{kind}",
            )
        )
    return out


def _r034(c: _Ctx) -> list:
    out = []
    for d in c.roots:
        if "assets" not in d.fm:
            continue
        line = _key_line(d, "assets")
        value = d.fm["assets"]
        if not isinstance(value, list):
            out.append(_fail("R-LINT-034", d.rel, line, "assets must be a list of <kind>:<path> strings"))
            continue
        seen = set()
        for entry in value:

            def add(message):
                out.append(_fail("R-LINT-034", d.rel, line, message))

            kind, sep, path = entry.partition(":")
            if not sep or not re.fullmatch(r"[a-z][a-z0-9-]*", kind) or not path:
                add(f"asset '{entry}' is not <kind>:<path>")
                continue
            if path.startswith("/") or "\\" in path:
                add(f"asset '{entry}': path must be relative with / separators")
            if ".." in path.split("/"):
                add(f"asset '{entry}': path contains ..")
            if path.endswith(".py"):
                add(f"asset '{entry}': path ends in .py")
            if kind == "python":
                add(f"asset '{entry}': python is never declared")
                continue
            if kind in seen:
                continue
            seen.add(kind)
            out.extend(_asset_kind_findings(c, d, line, kind))
    return out


_RULES = (
    _r001,
    _r002,
    _r003,
    _r004,
    _r005,
    _r006,
    _r007,
    _r008,
    _r009,
    _r010,
    _r011,
    _r013,
    _r014,
    _r015,
    _r016,
    _r017,
    _r018,
    _r019,
    _r024,
    _r031,
    _r032,
    _r034,
)


# --------------------------------------------------------------------------
# Library entry point
# --------------------------------------------------------------------------


def lint(paths, repo_root, strict: bool = False, judge=None) -> LintReport:
    repo_root = Path(repo_root)
    corpus = _load_dependency(repo_root, "corpus-loader").load_corpus(repo_root)
    ctx = _Ctx(corpus, repo_root, judge)
    findings = [f for rule in _RULES for f in rule(ctx)]
    for slug in ("citation-checker", "size-checker"):
        for f in _load_dependency(repo_root, slug).check(repo_root):
            findings.append(
                Finding(
                    _g(f, "rule_id"),
                    _g(f, "severity"),
                    _g(f, "file"),
                    _g(f, "line"),
                    _g(f, "message"),
                )
            )
    if paths is not None:
        roots = [(Path(p) if Path(p).is_absolute() else repo_root / p).resolve() for p in paths]

        def within(rel):
            target = (repo_root / rel).resolve()
            return any(target == r or r in target.parents for r in roots)

        findings = [f for f in findings if within(f.file)]
    return LintReport(findings, strict)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _usage(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    fmt, strict, repo_root, paths = "text", False, None, []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--strict":
            strict = True
        elif arg.split("=", 1)[0] in ("--format", "--repo-root"):
            flag, eq, value = arg.partition("=")
            if not eq:
                i += 1
                if i == len(args):
                    return _usage(f"{flag} needs a value")
                value = args[i]
            if flag == "--format":
                fmt = value
            else:
                repo_root = value
        elif arg.startswith("-"):
            return _usage(f"unknown argument {arg}")
        else:
            paths.append(arg)
        i += 1
    if fmt not in ("text", "json"):
        return _usage(f"--format must be json or text, not {fmt}")
    if repo_root is None:
        cwd = Path.cwd().resolve()
        root = next((p for p in [cwd, *cwd.parents] if (p / ".git").exists()), None)
        if root is None:
            return _usage("not in a git repository; pass --repo-root")
    else:
        root = Path(repo_root)
        if not root.is_dir():
            return _usage(f"cannot read repo root {repo_root}")
    for p in paths:
        if not (Path(p) if Path(p).is_absolute() else root / p).exists():
            return _usage(f"cannot read {p}")
    report = lint([Path(p) for p in paths] or None, root, strict=strict)
    if fmt == "json":
        print(json.dumps(report.to_json(), indent=2))
    else:
        for f in report.findings:
            print(f"{f.file}:{f.line}: {f.severity}: {f.rule_id}: {f.message}")
            if f.rationale is not None:
                print(f"  rationale: {f.rationale}")
        print(
            f"{report.hard_failures} hard failure(s), {report.warnings} warning(s), "
            f"{report.skipped} skipped"
        )
    return 1 if report.hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())
