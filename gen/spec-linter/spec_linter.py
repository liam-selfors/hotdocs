"""Spec linter: mechanically validates a spec corpus against SPEC_GUIDELINES.md."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

FM_TYPES = ("component-root", "product", "architecture", "var", "decision")
ALWAYS = ("id", "title", "status", "owners")
STATUSES = ("draft", "ratified", "deprecated")
LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "builds_on")
UNIT_TYPES = (
    "component-requirement",
    "component-interface-cli",
    "component-interface-library",
    "component-interface-data",
    "component-interface-guarantee",
    "component-acceptance",
    "component-constraints",
)
RFC_RE = re.compile(r"\b(MUST|REQUIRED|SHALL|SHOULD|RECOMMENDED|MAY|OPTIONAL)\b")
KIND_RE = re.compile(r"^Kind:\s*(compiled|generated-test|llm-judge)\s*$", re.M)
ENTRY_RE = re.compile(r"^- \*\*(.+?)\*\*(.*)$")
SECRET_RE = re.compile(r"^\s*[-*]\s*[`*]*sensitivity[`*]*\s*:[\s`*]*secret\b", re.I)
EXDEF_RE = re.compile(r"^\s*[-*]\s*[`*]*(example|default)[`*]*\s*:", re.I)
BOUNDED_RE = re.compile(r"bounded[- ]context", re.I)
DREF_RE = re.compile(r"\bD\d+\b")
USAGE = "usage: hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]"

_LOADED: dict = {}


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load_dep(repo_root, slug, name):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{name}.py"
    target = flat if flat.is_file() else base / name / "__init__.py"
    key = str(target.resolve())
    if key not in _LOADED:
        extra = {} if target is flat else {"submodule_search_locations": [str(target.parent)]}
        spec = importlib.util.spec_from_file_location(name, target, **extra)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        _LOADED[key] = mod
    return _LOADED[key]


def __getattr__(name):
    if name == "load_corpus":
        return _load_dep(_tool_root(), "corpus-loader", "corpus_loader").load_corpus
    raise AttributeError(name)


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

    @property
    def hard_failures(self) -> int:
        return sum(
            f.severity == "fail" or (self.strict and f.severity == "warn")
            for f in self.findings
        )

    @property
    def warnings(self) -> int:
        return sum(f.severity == "warn" for f in self.findings)

    @property
    def skipped(self) -> int:
        return sum(f.severity == "skipped" for f in self.findings)

    def to_json(self) -> dict:
        return {
            "findings": [f.to_json() for f in self.findings],
            "summary": {
                "hard_failures": self.hard_failures,
                "warnings": self.warnings,
                "skipped": self.skipped,
            },
        }


class _Ctx:
    def __init__(self, corpus, repo_root, judge):
        self.corpus = corpus
        self.repo_root = repo_root
        self.judge = judge
        self.docs = list(_get(corpus, "docs"))
        self.id_index = _get(corpus, "id_index")
        self.components = _get(corpus, "components")
        self.graph = _get(corpus, "graph")
        self.by_id = {(_get(d, "doc_type"), _get(d, "doc_id")): d for d in self.docs}
        self.findings: list = []
        self._lines: dict = {}

    def lines(self, doc):
        path = str(_get(doc, "path"))
        if path not in self._lines:
            self._lines[path] = Path(path).read_text(encoding="utf-8").splitlines()
        return self._lines[path]

    def add(self, rule, file, line, message, severity="fail", rationale=None):
        self.findings.append(Finding(rule, severity, file, line, message, rationale))

    def query(self, sql):
        return self.graph.execute(sql).fetchall()

    def of_type(self, *types):
        return [d for d in self.docs if _get(d, "doc_type") in types]


def _fm(doc):
    return _get(doc, "frontmatter") or {}


def _rel(doc):
    return _get(doc, "rel_path")


def _field_line(lines, name):
    pattern = re.compile(rf"{re.escape(name)}\s*:")
    return next((i for i, line in enumerate(lines, 1) if pattern.match(line)), 1)


def _section(lines, title):
    start, body = 0, []
    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            if start:
                break
            if line[3:].strip().lower() == title.lower():
                start = i
        elif start:
            body.append((i, line))
    return start, body


def _canon(path):
    i = path.index(min(path))
    return tuple(path[i:] + path[:i])


def _native_cycles(adj):
    found = set()

    def walk(start, cur, path):
        for nxt in adj.get(cur, []):
            if nxt == start:
                found.add(_canon(path))
            elif nxt not in path:
                walk(start, nxt, path + [nxt])

    for start in adj:
        walk(start, start, [start])
    return found


def _tokens(text):
    return set(re.findall(r"\w+", text.lower()))


def _ref_msg(edge_type, target, status):
    tail = "is deprecated" if status == "deprecated" else "does not exist"
    return f"{edge_type} references '{target}', which {tail}"


def _r001(ctx):
    for doc in ctx.of_type(*FM_TYPES):
        fm, rel, lines = _fm(doc), _rel(doc), ctx.lines(doc)
        for name in ALWAYS:
            if name not in fm:
                ctx.add("R-LINT-001", rel, 1, f"frontmatter is missing required field '{name}'")
        if "status" in fm and fm["status"] not in STATUSES:
            ctx.add("R-LINT-001", rel, _field_line(lines, "status"),
                    f"status '{fm['status']}' is not one of draft, ratified, deprecated")
        for name in LIST_FIELDS:
            if name in fm and not isinstance(fm[name], list):
                ctx.add("R-LINT-001", rel, _field_line(lines, name), f"'{name}' must be a list")
        if "sealed" in fm and not isinstance(fm["sealed"], bool):
            ctx.add("R-LINT-001", rel, _field_line(lines, "sealed"), "'sealed' must be a boolean")


def _r002(ctx):
    for doc in ctx.of_type(*FM_TYPES):
        fm, rel, lines = _fm(doc), _rel(doc), ctx.lines(doc)
        if fm.get("status") != "ratified":
            continue
        start, body = _section(lines, "Open questions")
        if any(line.strip() for _, line in body):
            ctx.add("R-LINT-002", rel, start, "ratified spec has a non-empty Open questions section")
        if not fm.get("last_ratified_commit"):
            ctx.add("R-LINT-002", rel, _field_line(lines, "status"),
                    "ratified spec lacks last_ratified_commit")


def _r003(ctx):
    rows = ctx.query(
        "SELECT e.source_id, e.target_id, e.edge_type, n.status FROM edges e "
        "LEFT JOIN nodes n ON n.id = e.target_id "
        "WHERE e.edge_type IN ('depends_on', 'realizes', 'uses_var') "
        "AND (n.id IS NULL OR n.status = 'deprecated') ORDER BY 1, 3, 2"
    )
    for src, tgt, edge_type, status in rows:
        doc = ctx.id_index[src]
        ctx.add("R-LINT-003", _rel(doc), _field_line(ctx.lines(doc), edge_type),
                _ref_msg(edge_type, tgt, status))
    for doc in ctx.of_type("architecture"):
        deps = _fm(doc).get("depends_on")
        for dep in deps if isinstance(deps, list) else []:
            status = _fm(ctx.id_index.get(dep)).get("status")
            if dep not in ctx.id_index or status == "deprecated":
                ctx.add("R-LINT-003", _rel(doc), _field_line(ctx.lines(doc), "depends_on"),
                        _ref_msg("depends_on", dep, status))


def _r004(ctx):
    rows = ctx.query(
        "WITH RECURSIVE walk(start_id, cur, path) AS ("
        " SELECT source_id, target_id, list_value(source_id) FROM edges"
        " WHERE edge_type = 'depends_on'"
        " UNION ALL"
        " SELECT w.start_id, e.target_id, list_append(w.path, w.cur) FROM walk w"
        " JOIN edges e ON e.source_id = w.cur AND e.edge_type = 'depends_on'"
        " WHERE NOT list_contains(w.path, w.cur)"
        ") SELECT DISTINCT path FROM walk WHERE cur = start_id"
    )
    cycles = {_canon(list(row[0])) for row in rows}
    adj = {}
    for doc in ctx.of_type("architecture"):
        deps = _fm(doc).get("depends_on")
        adj[_get(doc, "doc_id")] = deps if isinstance(deps, list) else []
    cycles |= _native_cycles(adj)
    for cycle in sorted(cycles):
        doc = ctx.id_index[cycle[0]]
        ctx.add("R-LINT-004", _rel(doc), _field_line(ctx.lines(doc), "depends_on"),
                "depends_on cycle: " + " -> ".join(cycle + (cycle[0],)))


def _r005_006(ctx):
    for doc in ctx.of_type("component-root"):
        fm, rel, lines = _fm(doc), _rel(doc), ctx.lines(doc)
        sealed = fm.get("sealed") is True
        if sealed and not fm.get("source_path"):
            ctx.add("R-LINT-005", rel, _field_line(lines, "sealed"), "sealed: true but no source_path")
        if fm.get("source_path") and not sealed:
            ctx.add("R-LINT-005", rel, _field_line(lines, "source_path"),
                    "source_path is set but sealed is not true")
    for doc in ctx.of_type("component-root"):
        fm = _fm(doc)
        if fm.get("sealed") is not True and not fm.get("realizes"):
            ctx.add("R-LINT-006", _rel(doc), 1, "non-sealed component has no realizes entries")


def _unit_ids(ctx, rule, doc_type, prefix):
    docs = ctx.of_type(doc_type)
    counts = Counter(_get(d, "doc_id") for d in docs)
    pattern = re.compile(rf"^{prefix}-[A-Z0-9]+-\d{{3}}$")
    for doc in docs:
        stem, rel, lines = _get(doc, "doc_id"), _rel(doc), ctx.lines(doc)
        if not pattern.match(stem):
            ctx.add(rule, rel, 1, f"'{stem}' is not a valid {prefix}-<comp>-NNN id")
        if counts[stem] > 1:
            ctx.add(rule, rel, 1, f"id '{stem}' is not unique")
        heading = next(((i, l[2:].strip()) for i, l in enumerate(lines, 1) if l.startswith("# ")), (1, None))
        if heading[1] != stem:
            ctx.add(rule, rel, heading[0], f"heading '{heading[1]}' does not match filename '{stem}'")
        if not RFC_RE.search(_get(doc, "body")):
            ctx.add(rule, rel, 1, f"{stem} uses no RFC 2119 keyword")


def _r007(ctx):
    _unit_ids(ctx, "R-LINT-007", "component-requirement", "R")


def _r008(ctx):
    rows = ctx.query(
        "SELECT n.id FROM nodes n WHERE n.kind = 'requirement' AND NOT EXISTS ("
        "SELECT 1 FROM edges e WHERE e.edge_type = 'covers' AND e.target_id = n.id) ORDER BY 1"
    )
    for (rid,) in rows:
        doc = ctx.by_id[("component-requirement", rid)]
        ctx.add("R-LINT-008", _rel(doc), 1, f"{rid} has no covering acceptance criterion")


def _covers_location(ctx, src):
    heading = re.compile(rf"^###\s+{re.escape(src)}\b")
    for doc in ctx.of_type("component-acceptance", "product"):
        lines = ctx.lines(doc)
        if _get(doc, "doc_type") == "component-acceptance":
            starts = [0] if _get(doc, "doc_id") == src else []
        else:
            starts = [i for i, line in enumerate(lines) if heading.match(line)]
        for start in starts:
            line = next((i + 1 for i in range(start, len(lines)) if "covers:" in lines[i].lower()), 1)
            return _rel(doc), line
    return src, 1


def _r009(ctx):
    rows = ctx.query(
        "SELECT e.source_id, e.target_id FROM edges e LEFT JOIN nodes n "
        "ON n.id = e.target_id AND n.kind IN ('requirement', 'capability') "
        "WHERE e.edge_type = 'covers' AND n.id IS NULL ORDER BY 1, 2"
    )
    for src, tgt in rows:
        rel, line = _covers_location(ctx, src)
        if tgt.startswith("R-"):
            msg = f"Covers: '{tgt}' looks like an R-id but does not resolve to a real requirement"
        elif tgt.startswith("P-"):
            msg = f"Covers: '{tgt}' looks like a P-id but does not resolve to a real capability"
        else:
            msg = f"Covers: '{tgt}' is neither an R-id nor a P-id"
        ctx.add("R-LINT-009", rel, line, msg)


def _r010(ctx):
    for doc in ctx.of_type("component-acceptance"):
        body, rel = _get(doc, "body"), _rel(doc)
        if not KIND_RE.search(body):
            ctx.add("R-LINT-010", rel, 1, "acceptance criterion is missing a valid 'Kind:' line")
        missing = [k for k in ("Given", "When", "Then") if not re.search(rf"^\s*{k}\b", body, re.M)]
        if missing:
            ctx.add("R-LINT-010", rel, 1,
                    "Given/When/Then block is incomplete: missing " + ", ".join(missing))


def _definition_entries(lines):
    entries = []
    for ln, line in _section(lines, "Definitions")[1]:
        m = ENTRY_RE.match(line)
        if m:
            entries.append((ln, m.group(1), [m.group(2)]))
        elif entries:
            entries[-1][2].append(line)
    return [(ln, term, "\n".join(parts).lstrip("—- \t").strip()) for ln, term, parts in entries]


def _r011_015(ctx):
    gloss = _get(ctx.corpus, "glossary_defs")
    for doc in ctx.of_type("component-root"):
        rel = _rel(doc)
        for ln, term, text in _definition_entries(ctx.lines(doc)):
            key = term.lower()
            if key not in gloss:
                continue
            gtext = gloss[key]
            gtokens = _tokens(gtext)
            ratio = len(_tokens(text) & gtokens) / max(len(gtokens), 1)
            if ratio >= 0.8:
                ctx.add("R-LINT-011", rel, ln,
                        f"Definitions entry '{term}' restates the glossary definition "
                        f"(token overlap {ratio:.2f} >= 0.8); only deltas belong here")
            elif ctx.judge is None:
                ctx.add("R-LINT-015", rel, ln,
                        f"R-LINT-015 skipped for '{term}': no model configured", "skipped")
            else:
                verdict = ctx.judge(term, text, gtext)
                if verdict is None:
                    ctx.add("R-LINT-015", rel, ln,
                            f"R-LINT-015 skipped for '{term}': the judge could not decide", "skipped")
                else:
                    conflicts, rationale = verdict
                    if conflicts:
                        ctx.add("R-LINT-015", rel, ln,
                                f"Definitions entry '{term}' conflicts with the glossary definition",
                                "fail", rationale)


def _r013(ctx):
    for doc in ctx.of_type("var"):
        lines = ctx.lines(doc)
        if not any(SECRET_RE.match(line) for line in lines):
            continue
        for i, line in enumerate(lines, 1):
            m = EXDEF_RE.match(line)
            if m:
                ctx.add("R-LINT-013", _rel(doc), i,
                        f"secret var declaration carries a '{m.group(1).lower()}' field")


def _relpath(ctx, path):
    return Path(path).resolve().relative_to(ctx.repo_root.resolve()).as_posix()


def _r014(ctx):
    files = sorted(str(f) for f in _get(ctx.corpus, "glossary_files"))
    if len(files) < 2:
        return
    if any(BOUNDED_RE.search(_get(d, "body")) for d in ctx.of_type("architecture")):
        return
    for f in files:
        if Path(f).name != "glossary.md":
            ctx.add("R-LINT-014", _relpath(ctx, f), 1,
                    "more than one glossary file exists without an architecture-level "
                    "bounded-context split decision")


def _r016(ctx):
    for doc in ctx.of_type(*UNIT_TYPES):
        if _get(doc, "has_frontmatter"):
            ctx.add("R-LINT-016", _rel(doc), 1,
                    "unit file carries a YAML frontmatter block; frontmatter belongs only on component.md")


def _r017(ctx):
    _unit_ids(ctx, "R-LINT-017", "component-interface-guarantee", "G")


def _r018(ctx):
    rows = ctx.query(
        "SELECT e.source_id, e.target_id, n.owner_component_id, n.id IS NULL AS missing, "
        "EXISTS (SELECT 1 FROM edges d WHERE d.edge_type = 'depends_on' "
        "AND d.source_id = e.source_id AND d.target_id = n.owner_component_id) AS listed "
        "FROM edges e LEFT JOIN nodes n ON n.id = e.target_id AND n.kind = 'guarantee' "
        "WHERE e.edge_type = 'depends_on_guarantees' ORDER BY 1, 2"
    )
    for src, tgt, owner, missing, listed in rows:
        doc = ctx.id_index[src]
        line = _field_line(ctx.lines(doc), "depends_on_guarantees")
        if missing:
            ctx.add("R-LINT-018", _rel(doc), line,
                    f"depends_on_guarantees references '{tgt}', which is not an existing guarantee id")
        elif not listed:
            ctx.add("R-LINT-018", _rel(doc), line,
                    f"depends_on_guarantees references '{tgt}', owned by '{owner}', "
                    f"which is not listed in depends_on")


def _r019(ctx):
    targets = [(_rel(d), ctx.lines(d)) for d in ctx.docs]
    targets += [
        (_relpath(ctx, g), Path(g).read_text(encoding="utf-8").splitlines())
        for g in _get(ctx.corpus, "glossary_files")
    ]
    for rel, lines in targets:
        for i, line in enumerate(lines, 1):
            if line != line.rstrip():
                ctx.add("R-LINT-019", rel, i, "line ends in trailing whitespace")


def _r024(ctx):
    for doc in ctx.of_type("component-root"):
        for ln, line in _section(ctx.lines(doc), "Purpose")[1]:
            for m in DREF_RE.finditer(line):
                ctx.add("R-LINT-024", _rel(doc), ln,
                        f"Purpose cites decision id '{m.group(0)}'; decision citations belong in Rationale")


def _r031(ctx):
    covered = {row[0] for row in ctx.query("SELECT DISTINCT target_id FROM edges WHERE edge_type = 'covers'")}
    for name, comp in sorted(ctx.components.items()):
        cli = _get(comp, "interface_cli")
        if cli is None:
            continue
        reqs = _get(comp, "requirements") or {}
        if not any(rid in covered and "interface/cli.md" in _get(r, "body") for rid, r in reqs.items()):
            ctx.add("R-LINT-031", _rel(cli), 1,
                    f"comp-{name} has interface/cli.md but no covered requirement cites it by path "
                    f"(see SPEC_GUIDELINES.md §5)", "warn")


def _r032(ctx):
    if not (ctx.repo_root / ".hotdocs-tool.json").exists():
        return
    gen = _tool_root() / "gen"
    for name in sorted(ctx.components):
        if (gen / name).is_dir():
            ctx.add("R-LINT-032", f"specs/components/{name}/component.md", 1,
                    f"component '{name}' would shadow the tool's own gen/{name}")


RULES = (
    _r001, _r002, _r003, _r004, _r005_006, _r007, _r008, _r009, _r010,
    _r011_015, _r013, _r014, _r016, _r017, _r018, _r019, _r024, _r031, _r032,
)


def _resolve(repo_root, p):
    p = Path(p)
    return (p if p.is_absolute() else repo_root / p).resolve()


def lint(paths, repo_root, strict=False, judge=None) -> LintReport:
    repo_root = Path(repo_root)
    corpus = _load_dep(repo_root, "corpus-loader", "corpus_loader").load_corpus(repo_root)
    ctx = _Ctx(corpus, repo_root, judge)
    for rule in RULES:
        rule(ctx)
    for slug, name in (("citation-checker", "citation_checker"), ("size-checker", "size_checker")):
        for item in _load_dep(repo_root, slug, name).check(repo_root):
            ctx.add(_get(item, "rule_id"), _get(item, "file"), _get(item, "line"),
                    _get(item, "message"), _get(item, "severity"))
    findings = ctx.findings
    if paths is not None:
        roots = [_resolve(repo_root, p) for p in paths]

        def keep(f):
            target = (repo_root / f.file).resolve()
            return any(target == r or r in target.parents for r in roots)

        findings = [f for f in findings if keep(f)]
    return LintReport(findings, strict)


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _git_root():
    cwd = Path.cwd().resolve()
    return next((p for p in (cwd, *cwd.parents) if (p / ".git").exists()), None)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    opts = {"--format": "text", "--repo-root": None}
    strict = False
    raw_paths = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        name, eq, value = tok.partition("=")
        if name in opts:
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(f"{name} requires a value")
                i += 1
                value = argv[i]
            opts[name] = value
        elif tok == "--strict":
            strict = True
        elif tok.startswith("-"):
            return _usage_error(f"unknown argument: {tok}")
        else:
            raw_paths.append(tok)
        i += 1
    fmt = opts["--format"]
    if fmt not in ("text", "json"):
        return _usage_error(f"invalid --format value: {fmt}")
    if opts["--repo-root"] is None:
        repo_root = _git_root()
        if repo_root is None:
            return _usage_error("not inside a git repository; pass --repo-root")
    else:
        repo_root = Path(opts["--repo-root"])
        if not repo_root.is_dir():
            return _usage_error(f"unreadable repo root: {repo_root}")
    paths = []
    for raw in raw_paths:
        resolved = _resolve(repo_root, raw)
        if not resolved.exists():
            return _usage_error(f"unreadable path: {raw}")
        paths.append(resolved)
    report = lint(paths or None, repo_root, strict)
    if fmt == "json":
        print(json.dumps(report.to_json(), indent=2))
    else:
        for f in report.findings:
            print(f"{f.file}:{f.line}: {f.severity}: {f.rule_id}: {f.message}")
        print(f"{report.hard_failures} hard failure(s), {report.warnings} warning(s), "
              f"{report.skipped} skipped")
    return 1 if report.hard_failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
