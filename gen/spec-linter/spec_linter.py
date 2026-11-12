"""Spec linter: mechanically validates a spec corpus against SPEC_GUIDELINES.md.

Library: ``lint(paths, repo_root, strict=False, judge=None) -> LintReport`` and
``load_corpus`` (corpus-loader's own function, re-exported unchanged).
CLI: ``main(argv)`` -- the tokens after ``hotdocs lint``.
"""
import argparse
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# --------------------------------------------------------------------------
# Dependency loading (repo_root first, then the tool root)
# --------------------------------------------------------------------------

_MODULES = {}


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _dep(repo_root, slug, module_name):
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    flat = directory / f"{module_name}.py"
    target = flat if flat.is_file() else directory / module_name / "__init__.py"
    key = str(target.resolve())
    if key not in _MODULES:
        locations = None if target == flat else [str(target.parent)]
        spec = importlib.util.spec_from_file_location(
            module_name, target, submodule_search_locations=locations
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        _MODULES[key] = module
    return _MODULES[key]


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


load_corpus = _dep(_tool_root(), "corpus-loader", "corpus_loader").load_corpus

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
    rationale: Optional[str] = None

    def to_json(self):
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
    findings: List[Finding] = field(default_factory=list)
    strict: bool = False

    @property
    def hard_failures(self):
        return sum(
            f.severity == "fail" or (self.strict and f.severity == "warn")
            for f in self.findings
        )

    @property
    def warnings(self):
        return sum(f.severity == "warn" for f in self.findings)

    @property
    def skipped(self):
        return sum(f.severity == "skipped" for f in self.findings)

    def to_json(self):
        return {
            "findings": [f.to_json() for f in self.findings],
            "summary": {
                "hard_failures": self.hard_failures,
                "warnings": self.warnings,
                "skipped": self.skipped,
            },
        }


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

_RFC2119 = re.compile(r"\b(MUST|SHOULD|MAY|SHALL|REQUIRED|RECOMMENDED|OPTIONAL)\b")
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
_ALWAYS = ("id", "title", "status", "owners")
_LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "builds_on")


class _Ctx:
    def __init__(self, root, corpus, judge):
        self.root = root
        self.docs = list(_get(corpus, "docs"))
        self.components = _get(corpus, "components")
        self.id_index = _get(corpus, "id_index")
        self.glossary_defs = _get(corpus, "glossary_defs")
        self.glossary_files = _get(corpus, "glossary_files")
        self.graph = _get(corpus, "graph")
        self.judge = judge

    def of_type(self, *types):
        return [d for d in self.docs if _get(d, "doc_type") in types]

    def query(self, sql):
        return self.graph.execute(sql).fetchall()


def _f(rule_id, file, line, message, severity="fail", rationale=None):
    return Finding(rule_id, severity, file, line, message, rationale)


def _lines(doc):
    return Path(_get(doc, "path")).read_text(encoding="utf-8").splitlines()


def _rel(doc):
    return _get(doc, "rel_path")


def _fm(doc):
    return _get(doc, "frontmatter")


def _list(fm, key):
    value = fm.get(key)
    return value if isinstance(value, list) else []


def _fm_line(lines, name):
    if [l.strip() for l in lines[:1]] == ["---"]:
        for number, line in enumerate(lines[1:], 2):
            if line.strip() == "---":
                break
            if re.match(rf"{re.escape(name)}\s*:", line):
                return number
    return 1


def _section(lines, title):
    head, body, inside = 0, [], False
    for number, line in enumerate(lines, 1):
        m = re.match(r"#{1,2}\s+(.*?)\s*$", line)
        if m:
            inside = m.group(1).lower() == title.lower()
            head = number if inside else head
        elif inside:
            body.append((number, line))
    return head, body


def _ref_finding(rule_id, doc, edge_type, target, missing):
    state = "does not exist" if missing else "is deprecated"
    return _f(
        rule_id,
        _rel(doc),
        _fm_line(_lines(doc), edge_type),
        f"{edge_type} references '{target}', which {state}",
    )


def _native_sccs(adj):
    reach = {}
    for start in adj:
        seen, stack = set(), list(adj[start])
        while stack:
            node = stack.pop()
            if node not in seen:
                seen.add(node)
                stack.extend(adj.get(node, []))
        reach[start] = seen
    return sorted(
        {
            tuple(sorted(b for b in reach[a] if a in reach.get(b, ())))
            for a in reach
            if a in reach[a]
        }
    )


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _definitions(lines):
    _, body = _section(lines, "Definitions")
    entries = []
    for number, line in body:
        m = re.match(r"- \*\*(.+?)\*\*(.*)$", line)
        if m:
            entries.append([number, m.group(1), [m.group(2)]])
        elif entries:
            entries[-1][2].append(line)
    return [
        (number, term, "\n".join(parts).lstrip("—- \t\r\n").rstrip())
        for number, term, parts in entries
    ]


def _covers_line(lines, start):
    return next(
        (n for n, l in enumerate(lines, 1) if n >= start and "Covers:" in l), start
    )


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------


def _r001(ctx):
    out = []
    for doc in ctx.of_type(*_FM_TYPES):
        fm, lines = _fm(doc), _lines(doc)
        for name in _ALWAYS:
            if name not in fm:
                out.append(_f("R-LINT-001", _rel(doc), 1, f"missing required frontmatter field '{name}'"))
        for name in _LIST_FIELDS:
            if name in fm and not isinstance(fm[name], list):
                out.append(_f("R-LINT-001", _rel(doc), _fm_line(lines, name), f"frontmatter field '{name}' must be a list"))
        if "sealed" in fm and not isinstance(fm["sealed"], bool):
            out.append(_f("R-LINT-001", _rel(doc), _fm_line(lines, "sealed"), "frontmatter field 'sealed' must be a boolean"))
    return out


def _r002(ctx):
    out = []
    for doc in ctx.of_type(*_FM_TYPES):
        fm = _fm(doc)
        if fm.get("status") == "ratified":
            lines = _lines(doc)
            head, body = _section(lines, "Open questions")
            if any(text.strip() for _, text in body):
                out.append(_f("R-LINT-002", _rel(doc), head, "status: ratified with a non-empty Open questions section"))
            if not fm.get("last_ratified_commit"):
                out.append(_f("R-LINT-002", _rel(doc), _fm_line(lines, "status"), "status: ratified without last_ratified_commit"))
    return out


def _r003(ctx):
    out = []
    rows = ctx.query(
        "SELECT e.edge_type, e.source_id, e.target_id, n.id "
        "FROM edges e LEFT JOIN nodes n ON n.id = e.target_id "
        "WHERE e.edge_type IN ('depends_on', 'realizes', 'uses_var') "
        "AND (n.id IS NULL OR n.status = 'deprecated') "
        "ORDER BY e.source_id, e.edge_type, e.target_id"
    )
    for edge_type, source, target, node in rows:
        out.append(_ref_finding("R-LINT-003", ctx.id_index[source], edge_type, target, node is None))
    # D13 residual: architecture docs' own depends_on (not in nodes/edges).
    for doc in ctx.of_type("architecture"):
        for target in _list(_fm(doc), "depends_on"):
            found = ctx.id_index.get(target)
            if found is None or _fm(found).get("status") == "deprecated":
                out.append(_ref_finding("R-LINT-003", doc, "depends_on", target, found is None))
    return out


def _r004(ctx):
    out = []
    rows = ctx.query(
        "WITH RECURSIVE dep AS ("
        "  SELECT DISTINCT source_id, target_id FROM edges WHERE edge_type = 'depends_on'"
        "), reach(start_id, cur_id) AS ("
        "  SELECT source_id, target_id FROM dep"
        "  UNION"
        "  SELECT r.start_id, d.target_id FROM reach r JOIN dep d ON d.source_id = r.cur_id"
        ") "
        "SELECT a.start_id, a.cur_id FROM reach a "
        "JOIN reach b ON a.start_id = b.cur_id AND a.cur_id = b.start_id "
        "ORDER BY 1, 2"
    )
    groups = {}
    for a, b in rows:
        groups.setdefault(a, set()).add(b)
    for members in sorted({tuple(sorted(m)) for m in groups.values()}):
        doc = ctx.id_index[members[0]]
        out.append(_f("R-LINT-004", _rel(doc), _fm_line(_lines(doc), "depends_on"), "depends_on cycle among " + ", ".join(members)))
    # D13 residual: architecture docs' own depends_on.
    arch = {_get(d, "doc_id"): d for d in ctx.of_type("architecture")}
    adj = {i: _list(_fm(d), "depends_on") for i, d in arch.items()}
    for members in _native_sccs(adj):
        doc = arch[members[0]]
        out.append(_f("R-LINT-004", _rel(doc), _fm_line(_lines(doc), "depends_on"), "depends_on cycle among " + ", ".join(members)))
    return out


def _r005_006(ctx):
    out = []
    for doc in ctx.of_type("component-root"):
        fm, lines = _fm(doc), _lines(doc)
        sealed = fm.get("sealed") is True
        source = bool(fm.get("source_path"))
        if sealed and not source:
            out.append(_f("R-LINT-005", _rel(doc), _fm_line(lines, "sealed"), "sealed: true without source_path"))
        if source and not sealed:
            out.append(_f("R-LINT-005", _rel(doc), _fm_line(lines, "source_path"), "source_path set but sealed is not true"))
        if not sealed and not _list(fm, "realizes"):
            out.append(_f("R-LINT-006", _rel(doc), _fm_line(lines, "realizes"), "non-sealed component has no realizes entries"))
    return out


def _unit_ids(ctx, rule_id, subdir, prefix):
    pattern = re.compile(rf"{prefix}-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{{3}}")
    out, seen = [], set()
    for name in sorted(ctx.components):
        for path in sorted((ctx.root / "specs" / "components" / name / subdir).glob("*.md")):
            if path.name == "README.md":
                continue
            rel = path.relative_to(ctx.root).as_posix()
            lines = path.read_text(encoding="utf-8").splitlines()
            stem = path.stem
            if not pattern.fullmatch(stem):
                out.append(_f(rule_id, rel, 1, f"filename '{path.name}' is not a {prefix}-<comp>-NNN id"))
            elif stem in seen:
                out.append(_f(rule_id, rel, 1, f"duplicate id '{stem}'"))
            seen.add(stem)
            number, heading = next(
                ((n, l) for n, l in enumerate(lines, 1) if l.startswith("# ")), (1, "")
            )
            if heading[2:].strip() != stem:
                out.append(_f(rule_id, rel, number, f"heading does not match id '{stem}'"))
            if not _RFC2119.search("\n".join(lines)):
                out.append(_f(rule_id, rel, 1, "no RFC 2119 keyword"))
    return out


def _r007(ctx):
    return _unit_ids(ctx, "R-LINT-007", "requirements", "R")


def _r017(ctx):
    return _unit_ids(ctx, "R-LINT-017", "interface/guarantees", "G")


def _r008(ctx):
    files = {_get(d, "doc_id"): _rel(d) for d in ctx.of_type("component-requirement")}
    rows = ctx.query(
        "SELECT n.id FROM nodes n WHERE n.kind = 'requirement' "
        "AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.edge_type = 'covers' AND e.target_id = n.id) "
        "ORDER BY n.id"
    )
    return [
        _f("R-LINT-008", files[rid], 1, f"{rid} has no covering acceptance criterion")
        for (rid,) in rows
    ]


def _r009(ctx):
    locations = {}
    for doc in ctx.of_type("component-acceptance"):
        locations[_get(doc, "doc_id")] = (_rel(doc), _covers_line(_lines(doc), 1))
    for doc in ctx.of_type("product"):
        lines = _lines(doc)
        for number, line in enumerate(lines, 1):
            m = re.match(r"###\s+(CS-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)", line)
            if m:
                locations[m.group(1)] = (_rel(doc), _covers_line(lines, number))
    rows = ctx.query(
        "SELECT e.source_id, e.target_id FROM edges e WHERE e.edge_type = 'covers' "
        "AND NOT EXISTS (SELECT 1 FROM nodes n WHERE n.id = e.target_id "
        "AND n.kind IN ('requirement', 'capability')) "
        "ORDER BY e.source_id, e.target_id"
    )
    out = []
    for source, target in rows:
        file, line = locations.get(source, (source, 1))
        if target.startswith("R-"):
            message = f"Covers: references R-id '{target}', which does not exist"
        elif target.startswith("P-"):
            message = f"Covers: references P-id '{target}', which does not exist"
        else:
            message = f"Covers: target '{target}' is neither an R-id nor a P-id"
        out.append(_f("R-LINT-009", file, line, message))
    return out


def _r010(ctx):
    out = []
    for doc in ctx.of_type("component-acceptance"):
        text = "\n".join(_lines(doc))
        if not re.search(r"^Kind:\s*(compiled|generated-test|llm-judge)\s*$", text, re.M):
            out.append(_f("R-LINT-010", _rel(doc), 1, "acceptance criterion has no Kind:"))
        missing = [kw for kw in ("Given", "When", "Then") if not re.search(rf"^\s*{kw}\b", text, re.M)]
        if missing:
            out.append(_f("R-LINT-010", _rel(doc), 1, "incomplete Given/When/Then block, missing " + ", ".join(missing)))
    return out


def _r011_015(ctx):
    out = []
    for doc in ctx.of_type("component-root"):
        for number, term, text in _definitions(_lines(doc)):
            gloss = ctx.glossary_defs.get(term.lower())
            if gloss is None:
                continue
            gloss_tokens = _tokens(gloss)
            ratio = len(_tokens(text) & gloss_tokens) / max(len(gloss_tokens), 1)
            if ratio >= 0.8:
                out.append(_f("R-LINT-011", _rel(doc), number, f"Definitions entry '{term}' restates the glossary definition (overlap {ratio:.2f})"))
            elif ctx.judge is None:
                out.append(_f("R-LINT-015", _rel(doc), number, f"skipped: no model configured to judge Definitions entry '{term}'", "skipped"))
            else:
                verdict = ctx.judge(term, text, gloss)
                if verdict is None:
                    out.append(_f("R-LINT-015", _rel(doc), number, f"skipped: judge could not evaluate Definitions entry '{term}'", "skipped"))
                else:
                    conflicts, rationale = verdict
                    if conflicts:
                        out.append(_f("R-LINT-015", _rel(doc), number, f"Definitions entry '{term}' conflicts with the glossary definition", "fail", rationale))
    return out


def _r013(ctx):
    out = []
    for doc in ctx.of_type("var"):
        fields = {}
        for number, line in enumerate(_lines(doc), 1):
            m = re.match(r"\s*-\s+(\w+)\s*:\s*(.*)$", re.sub(r"[*`]", "", line))
            if m:
                fields.setdefault(m.group(1).lower(), (number, m.group(2).strip().lower()))
        if fields.get("sensitivity", (0, ""))[1].startswith("secret"):
            for name in ("example", "default"):
                if name in fields:
                    out.append(_f("R-LINT-013", _rel(doc), fields[name][0], f"sensitivity: secret declaration carries '{name}'"))
    return out


def _abs_rel(ctx, path):
    return Path(path).resolve().relative_to(ctx.root.resolve()).as_posix()


def _r014(ctx):
    files = sorted(Path(p) for p in ctx.glossary_files)
    split = any(
        re.search(r"bounded[- ]context", _get(d, "body"), re.I)
        for d in ctx.of_type("architecture")
    )
    if len(files) > 1 and not split:
        return [
            _f("R-LINT-014", _abs_rel(ctx, p), 1, "more than one glossary file without an architecture-level bounded-context split decision")
            for p in files
            if p.name != "glossary.md"
        ]
    return []


def _r016(ctx):
    return [
        _f("R-LINT-016", _rel(doc), 1, "unit file carries a frontmatter block")
        for doc in ctx.of_type(*_UNIT_TYPES)
        if _get(doc, "has_frontmatter")
    ]


def _r018(ctx):
    rows = ctx.query(
        "SELECT e.source_id, e.target_id, n.owner_component_id, "
        "EXISTS (SELECT 1 FROM edges d WHERE d.edge_type = 'depends_on' "
        "AND d.source_id = e.source_id AND d.target_id = n.owner_component_id) AS listed "
        "FROM edges e LEFT JOIN nodes n ON n.id = e.target_id AND n.kind = 'guarantee' "
        "WHERE e.edge_type = 'depends_on_guarantees' "
        "ORDER BY e.source_id, e.target_id"
    )
    out = []
    for source, target, owner, listed in rows:
        doc = ctx.id_index[source]
        line = _fm_line(_lines(doc), "depends_on_guarantees")
        if owner is None:
            out.append(_f("R-LINT-018", _rel(doc), line, f"depends_on_guarantees references '{target}', which does not exist"))
        elif not listed:
            out.append(_f("R-LINT-018", _rel(doc), line, f"depends_on_guarantees references '{target}', owned by {owner}, which is not in depends_on"))
    return out


def _r019(ctx):
    files = [(_rel(d), Path(_get(d, "path"))) for d in ctx.docs]
    files += [(_abs_rel(ctx, p), Path(p)) for p in ctx.glossary_files]
    out = []
    for rel, path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line != line.rstrip():
                out.append(_f("R-LINT-019", rel, number, "trailing whitespace"))
    return out


def _r024(ctx):
    out = []
    for doc in ctx.of_type("component-root"):
        _, body = _section(_lines(doc), "Purpose")
        for number, line in body:
            if re.search(r"\bD\d+\b", line):
                out.append(_f("R-LINT-024", _rel(doc), number, "Purpose cites a decision id; move it to Rationale"))
    return out


def _r031(ctx):
    covered = {t for (t,) in ctx.query("SELECT DISTINCT target_id FROM edges WHERE edge_type = 'covers'")}
    out = []
    for name in sorted(ctx.components):
        comp = ctx.components[name]
        cli = _get(comp, "interface_cli")
        if cli is None:
            continue
        requirements = _get(comp, "requirements")
        if not any(
            rid in covered and "interface/cli.md" in _get(req, "body")
            for rid, req in requirements.items()
        ):
            out.append(_f("R-LINT-031", _rel(cli), 1, f"comp-{name}: no covered requirement cites interface/cli.md (see SPEC_GUIDELINES.md §5)", "warn"))
    return out


def _r032(ctx):
    out = []
    if (ctx.root / ".hotdocs-tool.json").exists():
        tool_gen = _tool_root() / "gen"
        for name in sorted(ctx.components):
            if (tool_gen / name).is_dir():
                out.append(_f("R-LINT-032", f"specs/components/{name}/component.md", 1, f"component '{name}' would shadow the tool's own gen/{name}/"))
    return out


_RULES = (
    _r001, _r002, _r003, _r004, _r005_006, _r007, _r008, _r009, _r010,
    _r011_015, _r013, _r014, _r016, _r017, _r018, _r019, _r024, _r031, _r032,
)

# --------------------------------------------------------------------------
# Library entry point
# --------------------------------------------------------------------------


def _within(target, scopes):
    return any(target == scope or scope in target.parents for scope in scopes)


def lint(paths: Optional[List[Path]], repo_root: Path, strict: bool = False, judge=None) -> LintReport:
    root = Path(repo_root)
    corpus = _dep(root, "corpus-loader", "corpus_loader").load_corpus(root)
    ctx = _Ctx(root, corpus, judge)
    findings = sorted(
        (f for rule in _RULES for f in rule(ctx)),
        key=lambda f: (f.file, f.line, f.rule_id, f.message),
    )
    for slug, module_name in (("citation-checker", "citation_checker"), ("size-checker", "size_checker")):
        for item in _dep(root, slug, module_name).check(root):
            findings.append(
                Finding(
                    _get(item, "rule_id"),
                    _get(item, "severity"),
                    _get(item, "file"),
                    _get(item, "line"),
                    _get(item, "message"),
                )
            )
    if paths is not None:
        scopes = [(root / p).resolve() for p in paths]
        findings = [f for f in findings if _within((root / f.file).resolve(), scopes)]
    return LintReport(findings, strict)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _git_root():
    return subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    ).stdout.strip()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs lint")
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--repo-root")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2
    repo_root = Path(args.repo_root or _git_root())
    paths = [Path(p).resolve() for p in args.paths]
    if not repo_root.is_dir() or any(not p.exists() for p in paths):
        print("hotdocs lint: unreadable path", file=sys.stderr)
        return 2
    report = lint(paths or None, repo_root, strict=args.strict)
    if args.format == "json":
        print(json.dumps(report.to_json(), indent=2))
    else:
        for f in report.findings:
            print(f"{f.file}:{f.line}: {f.severity} {f.rule_id}: {f.message}")
        print(
            f"{report.hard_failures} hard failure(s), "
            f"{report.warnings} warning(s), {report.skipped} skipped"
        )
    return 1 if report.hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())