"""Spec Linter: mechanically validates a spec corpus against SPEC_GUIDELINES.md."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Dependency loading
# ---------------------------------------------------------------------------

_LOADED: dict = {}


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_path(base: Path, name: str):
    flat = base / f"{name}.py"
    target = flat if flat.exists() else base / name / "__init__.py"
    key = str(target.resolve())
    mod = _LOADED.get(key)
    if mod is None:
        spec = importlib.util.spec_from_file_location(
            name,
            target,
            submodule_search_locations=None if target == flat else [str(target.parent)],
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        _LOADED[key] = mod
    sys.modules[name] = mod
    return mod


def _load_dep(slug: str, repo_root: Path):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    return _load_path(base, slug.replace("-", "_"))


def _g(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


load_corpus = _load_path(_tool_root() / "gen" / "corpus-loader", "corpus_loader").load_corpus


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Context and text helpers
# ---------------------------------------------------------------------------

FM_TYPES = {"component-root", "product", "architecture", "var", "decision"}
UNIT_TYPES = {
    "component-requirement",
    "component-interface-cli",
    "component-interface-library",
    "component-interface-data",
    "component-interface-guarantee",
    "component-acceptance",
    "component-constraints",
}
LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "builds_on")
RFC = re.compile(r"\b(MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)\b")
ENTRY = re.compile(r"^\s*[-*]\s+\*\*(.+?)\*\*(.*)$")
BULLET = re.compile(r"^\s*[-*]\s+[`*]*([A-Za-z_]+)[`*]*\s*:\s*(.*)$")
KIND_LINE = re.compile(r"^Kind:\s*(compiled|generated-test|llm-judge)\s*$")
KIND_NAME = re.compile(r"[a-z][a-z0-9-]*")
DECISION = re.compile(r"\bD\d+\b")
ASSET_SECTIONS = (
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
)


class _Ctx:
    def __init__(self, repo_root: Path, corpus, judge):
        self.repo_root = repo_root
        self.corpus = corpus
        self.judge = judge
        self.docs = list(_g(corpus, "docs"))
        self.graph = _g(corpus, "graph")
        self.findings: list = []
        self._cache: dict = {}

    def add(self, rule_id, severity, file, line, message, rationale=None):
        self.findings.append(Finding(rule_id, severity, file, line, message, rationale))

    def q(self, sql):
        return self.graph.execute(sql).fetchall()

    def lines(self, rel):
        if rel not in self._cache:
            self._cache[rel] = (self.repo_root / rel).read_text(encoding="utf-8").splitlines()
        return self._cache[rel]

    def key_line(self, rel, key):
        lines = self.lines(rel)
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    break
                if lines[i].startswith(key + ":"):
                    return i + 1
        return 1

    def of_type(self, *types):
        return [d for d in self.docs if _g(d, "doc_type") in types]


def _section(lines, name):
    for i, line in enumerate(lines):
        if line.strip() == f"## {name}":
            out = []
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    break
                out.append((j + 1, lines[j]))
            return i + 1, out
    return None, []


def _comp_file(comp_id: str) -> str:
    return f"specs/components/{comp_id.removeprefix('comp-')}/component.md"


def _native_cycles(pairs):
    graph: dict = {}
    for a, b in pairs:
        graph.setdefault(a, set()).add(b)
    reach = {}
    for a in graph:
        seen: set = set()
        stack = list(graph[a])
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(graph.get(x, ()))
        reach[a] = seen
    return sorted(
        {
            tuple(sorted(b for b in reach if a in reach[b] and b in reach[a]))
            for a in reach
            if a in reach[a]
        }
    )


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def rule_001(ctx):
    for d in ctx.of_type(*FM_TYPES):
        fm = _g(d, "frontmatter")
        rel = _g(d, "rel_path")
        for f in ("id", "title", "status", "owners"):
            if f not in fm:
                ctx.add("R-LINT-001", "fail", rel, 1, f"missing required frontmatter field '{f}'")
        for f in LIST_FIELDS:
            if f in fm and not isinstance(fm[f], list):
                ctx.add("R-LINT-001", "fail", rel, ctx.key_line(rel, f),
                        f"frontmatter field '{f}' must be a list")
        if "sealed" in fm and not isinstance(fm["sealed"], bool):
            ctx.add("R-LINT-001", "fail", rel, ctx.key_line(rel, "sealed"),
                    "frontmatter field 'sealed' must be a boolean")


def rule_002(ctx):
    for d in ctx.of_type(*FM_TYPES):
        fm = _g(d, "frontmatter")
        rel = _g(d, "rel_path")
        if fm.get("status") == "ratified":
            heading, sec = _section(ctx.lines(rel), "Open questions")
            if any(t.strip() for _, t in sec):
                ctx.add("R-LINT-002", "fail", rel, heading,
                        "status: ratified with a non-empty Open questions section")
            if not fm.get("last_ratified_commit"):
                ctx.add("R-LINT-002", "fail", rel, ctx.key_line(rel, "status"),
                        "status: ratified without last_ratified_commit")


def rule_003(ctx):
    rows = ctx.q(
        "SELECT DISTINCT e.source_id, e.target_id, e.edge_type, n.status "
        "FROM edges e LEFT JOIN nodes n ON n.id = e.target_id "
        "WHERE e.edge_type IN ('depends_on', 'realizes', 'uses_var') "
        "AND (n.id IS NULL OR n.status = 'deprecated') "
        "ORDER BY e.source_id, e.edge_type, e.target_id"
    )
    for src, tgt, etype, status in rows:
        rel = _comp_file(src)
        what = "is deprecated" if status == "deprecated" else "does not exist"
        ctx.add("R-LINT-003", "fail", rel, ctx.key_line(rel, etype),
                f"{etype} references '{tgt}', which {what}")
    # Residual native check (D13): architecture-doc depends_on.
    id_index = _g(ctx.corpus, "id_index")
    for d in ctx.of_type("architecture"):
        rel = _g(d, "rel_path")
        for dep in _g(d, "frontmatter").get("depends_on") or []:
            target = id_index.get(dep)
            if target is None:
                ctx.add("R-LINT-003", "fail", rel, ctx.key_line(rel, "depends_on"),
                        f"depends_on references '{dep}', which does not exist")
            elif _g(target, "frontmatter").get("status") == "deprecated":
                ctx.add("R-LINT-003", "fail", rel, ctx.key_line(rel, "depends_on"),
                        f"depends_on references '{dep}', which is deprecated")


def rule_004(ctx):
    rows = ctx.q(
        "WITH RECURSIVE reach(src, dst) AS ("
        " SELECT source_id, target_id FROM edges WHERE edge_type = 'depends_on'"
        " UNION"
        " SELECT r.src, e.target_id FROM reach r JOIN edges e"
        " ON e.source_id = r.dst AND e.edge_type = 'depends_on'"
        ") SELECT a.src, a.dst FROM reach a JOIN reach b"
        " ON a.src = b.dst AND a.dst = b.src"
    )
    mutual: dict = {}
    for a, b in rows:
        mutual.setdefault(a, set()).add(b)
    for cycle in sorted({tuple(sorted(s)) for s in mutual.values()}):
        rel = _comp_file(cycle[0])
        ctx.add("R-LINT-004", "fail", rel, ctx.key_line(rel, "depends_on"),
                "depends_on cycle: " + ", ".join(cycle))
    # Residual native check (D13): architecture-doc depends_on.
    arch = {_g(d, "doc_id"): _g(d, "rel_path") for d in ctx.of_type("architecture")}
    pairs = [
        (_g(d, "doc_id"), dep)
        for d in ctx.of_type("architecture")
        for dep in _g(d, "frontmatter").get("depends_on") or []
    ]
    for cycle in _native_cycles(pairs):
        rel = arch[cycle[0]]
        ctx.add("R-LINT-004", "fail", rel, ctx.key_line(rel, "depends_on"),
                "depends_on cycle: " + ", ".join(cycle))


def rule_005_006(ctx):
    for d in ctx.of_type("component-root"):
        fm = _g(d, "frontmatter")
        rel = _g(d, "rel_path")
        sealed = fm.get("sealed") is True
        if sealed and not fm.get("source_path"):
            ctx.add("R-LINT-005", "fail", rel, ctx.key_line(rel, "sealed"),
                    "sealed: true without source_path")
        if not sealed and "source_path" in fm:
            ctx.add("R-LINT-005", "fail", rel, ctx.key_line(rel, "source_path"),
                    "source_path set but sealed is not true")
        if not sealed and not fm.get("realizes"):
            ctx.add("R-LINT-006", "fail", rel, ctx.key_line(rel, "realizes"),
                    "non-sealed component has no realizes entries")


def _unit_ids(ctx, rule_id, doc_type, prefix):
    pat = re.compile(rf"^{prefix}-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{{3}}$")
    units = ctx.of_type(doc_type)
    counts = Counter(Path(_g(d, "rel_path")).stem for d in units)
    for d in units:
        rel = _g(d, "rel_path")
        stem = Path(rel).stem
        lines = ctx.lines(rel)
        if not pat.match(stem):
            ctx.add(rule_id, "fail", rel, 1, f"filename '{stem}' is not a {prefix}-<comp>-NNN id")
        if counts[stem] > 1:
            ctx.add(rule_id, "fail", rel, 1, f"id '{stem}' is not unique")
        line_no, heading = next(
            ((i + 1, l) for i, l in enumerate(lines) if l.startswith("# ")), (1, "")
        )
        if heading[2:].strip() != stem:
            ctx.add(rule_id, "fail", rel, line_no, f"heading does not match filename '{stem}'")
        if not RFC.search("\n".join(lines)):
            ctx.add(rule_id, "fail", rel, 1, f"'{stem}' uses no RFC 2119 keyword")


def rule_007(ctx):
    _unit_ids(ctx, "R-LINT-007", "component-requirement", "R")


def rule_017(ctx):
    _unit_ids(ctx, "R-LINT-017", "component-interface-guarantee", "G")


def rule_008(ctx):
    files = {_g(d, "doc_id"): _g(d, "rel_path") for d in ctx.of_type("component-requirement")}
    rows = ctx.q(
        "SELECT DISTINCT n.id FROM nodes n WHERE n.kind = 'requirement' "
        "AND n.id NOT IN (SELECT target_id FROM edges "
        "WHERE edge_type = 'covers' AND target_id IS NOT NULL) ORDER BY n.id"
    )
    for (rid,) in rows:
        ctx.add("R-LINT-008", "fail", files[rid], 1,
                f"{rid} has no covering acceptance criterion")


def rule_009(ctx):
    locs = {}
    for d in ctx.of_type("component-acceptance"):
        rel = _g(d, "rel_path")
        lines = ctx.lines(rel)
        idx = next((i for i, l in enumerate(lines) if "Covers:" in l), 0)
        locs[_g(d, "doc_id")] = (rel, idx + 1)
    for d in ctx.of_type("product"):
        rel = _g(d, "rel_path")
        lines = ctx.lines(rel)
        for i, l in enumerate(lines):
            m = re.match(r"^###\s+(CS-[\w-]+)", l)
            if m:
                line_no = i + 1
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith("#"):
                        break
                    if "Covers:" in lines[j]:
                        line_no = j + 1
                        break
                locs[m.group(1)] = (rel, line_no)
    rows = ctx.q(
        "SELECT DISTINCT e.source_id, e.target_id FROM edges e "
        "WHERE e.edge_type = 'covers' AND e.target_id NOT IN "
        "(SELECT id FROM nodes WHERE kind IN ('requirement', 'capability')) "
        "ORDER BY 1, 2"
    )
    for src, tgt in rows:
        rel, line_no = locs[src]
        if tgt.startswith("R-"):
            msg = f"Covers: '{tgt}' does not resolve to a real R-id"
        elif tgt.startswith("P-"):
            msg = f"Covers: '{tgt}' does not resolve to a real P-id"
        else:
            msg = f"Covers: '{tgt}' is neither an R-id nor a P-id"
        ctx.add("R-LINT-009", "fail", rel, line_no, msg)


def rule_010(ctx):
    for d in ctx.of_type("component-acceptance"):
        rel = _g(d, "rel_path")
        lines = ctx.lines(rel)
        ci = next((i for i, l in enumerate(lines) if "Covers:" in l), 0)
        if not any(KIND_LINE.match(l) for l in lines[ci:]):
            ctx.add("R-LINT-010", "fail", rel, 1, "acceptance criterion has no Kind: line")
        text = "\n".join(lines)
        for kw in ("Given", "When", "Then"):
            if not re.search(rf"^\s*{kw}\b", text, re.M):
                ctx.add("R-LINT-010", "fail", rel, 1,
                        f"acceptance criterion's Given/When/Then block has no {kw} step")


def _definition_entries(sec):
    entries = []
    for line_no, text in sec:
        m = ENTRY.match(text)
        if m:
            entries.append([m.group(1).strip(), line_no, [m.group(2).lstrip("—- \t")]])
        elif entries:
            entries[-1][2].append(text)
    return [(t, ln, "\n".join(parts).strip()) for t, ln, parts in entries]


def rule_011_015(ctx):
    glossary = _g(ctx.corpus, "glossary_defs")
    for d in ctx.of_type("component-root"):
        rel = _g(d, "rel_path")
        _, sec = _section(ctx.lines(rel), "Definitions")
        for term, line_no, local in _definition_entries(sec):
            key = term.lower()
            if key not in glossary:
                continue
            gloss = glossary[key]
            g_tokens = set(re.findall(r"\w+", gloss.lower()))
            l_tokens = set(re.findall(r"\w+", local.lower()))
            if len(g_tokens & l_tokens) / max(len(g_tokens), 1) >= 0.8:
                ctx.add("R-LINT-011", "fail", rel, line_no,
                        f"Definitions entry for '{term}' restates the glossary definition")
                continue
            if ctx.judge is None:
                ctx.add("R-LINT-015", "skipped", rel, line_no,
                        f"meaning check for '{term}' skipped: no model configured")
                continue
            result = ctx.judge(term, local, gloss)
            if result is None:
                ctx.add("R-LINT-015", "skipped", rel, line_no,
                        f"meaning check for '{term}' skipped: the judge could not decide")
                continue
            conflicts, rationale = result
            if conflicts:
                ctx.add("R-LINT-015", "fail", rel, line_no,
                        f"Definitions entry for '{term}' conflicts with the glossary definition",
                        rationale)


def rule_013(ctx):
    for d in ctx.of_type("var"):
        rel = _g(d, "rel_path")
        fields: dict = {}
        for i, l in enumerate(ctx.lines(rel)):
            m = BULLET.match(l)
            if m:
                fields.setdefault(m.group(1).lower(), (i + 1, m.group(2).strip(" `*")))
        if fields.get("sensitivity", (0, ""))[1] == "secret":
            for f in ("example", "default"):
                if f in fields:
                    ctx.add("R-LINT-013", "fail", rel, fields[f][0],
                            f"sensitivity: secret declaration carries a '{f}' field")


def rule_014(ctx):
    files = sorted(
        Path(p).resolve().relative_to(ctx.repo_root).as_posix()
        for p in _g(ctx.corpus, "glossary_files")
    )
    if len(files) > 1:
        split = any(
            re.search(r"bounded[- ]context", _g(d, "body").lower())
            for d in ctx.of_type("architecture")
        )
        if not split:
            ctx.add("R-LINT-014", "fail", files[1], 1,
                    "more than one glossary file (" + ", ".join(files)
                    + ") without an architecture-level bounded-context split decision")


def rule_016(ctx):
    for d in ctx.of_type(*UNIT_TYPES):
        if _g(d, "has_frontmatter"):
            ctx.add("R-LINT-016", "fail", _g(d, "rel_path"), 1,
                    "unit file carries a frontmatter block")


def rule_018(ctx):
    rows = ctx.q(
        "SELECT DISTINCT e.source_id, e.target_id, n.id, n.owner_component_id, "
        "EXISTS (SELECT 1 FROM edges d WHERE d.edge_type = 'depends_on' "
        "AND d.source_id = e.source_id AND d.target_id = n.owner_component_id) "
        "FROM edges e LEFT JOIN nodes n ON n.id = e.target_id AND n.kind = 'guarantee' "
        "WHERE e.edge_type = 'depends_on_guarantees' ORDER BY 1, 2"
    )
    for src, tgt, nid, owner, listed in rows:
        rel = _comp_file(src)
        line_no = ctx.key_line(rel, "depends_on_guarantees")
        if nid is None:
            ctx.add("R-LINT-018", "fail", rel, line_no,
                    f"depends_on_guarantees references '{tgt}', which does not exist")
        elif not listed:
            ctx.add("R-LINT-018", "fail", rel, line_no,
                    f"depends_on_guarantees references '{tgt}', owned by {owner}, "
                    f"which is not in depends_on")


def rule_019(ctx):
    rels = [_g(d, "rel_path") for d in ctx.docs] + [
        Path(p).resolve().relative_to(ctx.repo_root).as_posix()
        for p in _g(ctx.corpus, "glossary_files")
    ]
    for rel in rels:
        for i, l in enumerate(ctx.lines(rel)):
            if l != l.rstrip():
                ctx.add("R-LINT-019", "fail", rel, i + 1, "line ends in trailing whitespace")


def rule_024(ctx):
    for d in ctx.of_type("component-root"):
        rel = _g(d, "rel_path")
        _, sec = _section(ctx.lines(rel), "Purpose")
        for line_no, text in sec:
            for m in DECISION.finditer(text):
                ctx.add("R-LINT-024", "fail", rel, line_no,
                        f"Purpose cites decision {m.group(0)}; move it to Rationale")


def rule_031(ctx):
    covered = {r[0] for r in ctx.q("SELECT DISTINCT target_id FROM edges WHERE edge_type = 'covers'")}
    for slug, comp in sorted(_g(ctx.corpus, "components").items()):
        cli = _g(comp, "interface_cli")
        if cli is None:
            continue
        ok = any(
            "interface/cli.md" in _g(r, "body") and _g(r, "doc_id") in covered
            for r in _g(comp, "requirements").values()
        )
        if not ok:
            ctx.add("R-LINT-031", "warn", _g(cli, "rel_path"), 1,
                    f"comp-{slug} has interface/cli.md but no covered requirement citing it "
                    f"(SPEC_GUIDELINES.md §5)")


def rule_032(ctx):
    if (ctx.repo_root / ".hotdocs-tool.json").exists():
        gen = _tool_root() / "gen"
        for slug in sorted(_g(ctx.corpus, "components")):
            if (gen / slug).is_dir():
                ctx.add("R-LINT-032", "fail", f"specs/components/{slug}/component.md", 1,
                        f"component '{slug}' would shadow the tool's gen/{slug}/")


def rule_034(ctx):
    tool = _tool_root()
    for d in ctx.of_type("component-root"):
        fm = _g(d, "frontmatter")
        if "assets" not in fm:
            continue
        rel = _g(d, "rel_path")
        line_no = ctx.key_line(rel, "assets")

        def add(msg):
            ctx.add("R-LINT-034", "fail", rel, line_no, msg)

        assets = fm["assets"]
        if not isinstance(assets, list):
            add("assets must be a list of <kind>:<path> strings")
            continue
        deps = fm.get("depends_on") or []
        seen: set = set()
        for entry in assets:
            kind, sep, path = entry.partition(":")
            if not sep or not KIND_NAME.fullmatch(kind) or not path:
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
            defn = ctx.repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"
            adapter = Path("gen") / f"kind-{kind}" / f"kind_{kind}.py"
            if not defn.exists() and not (ctx.repo_root / adapter).exists() \
                    and not (tool / adapter).exists():
                add(f"asset kind '{kind}' has no definition")
            if defn.exists():
                dl = defn.read_text(encoding="utf-8").splitlines()
                for name in ASSET_SECTIONS:
                    heading, sec = _section(dl, name)
                    if heading is None:
                        add(f"asset kind '{kind}' definition lacks section '{name}'")
                    elif not any(t.strip() for _, t in sec):
                        add(f"asset kind '{kind}' definition has empty section '{name}'")
                if f"comp-kind-{kind}" not in deps:
                    add(f"asset kind '{kind}' is defined in this repository; "
                        f"depends_on must list comp-kind-{kind}")


_RULES = (
    rule_001, rule_002, rule_003, rule_004, rule_005_006, rule_007, rule_008,
    rule_009, rule_010, rule_011_015, rule_013, rule_014, rule_016, rule_017,
    rule_018, rule_019, rule_024, rule_031, rule_032, rule_034,
)


# ---------------------------------------------------------------------------
# Library entry point
# ---------------------------------------------------------------------------


def lint(paths, repo_root, strict: bool = False, judge=None) -> LintReport:
    repo_root = Path(repo_root).resolve()
    corpus = _load_dep("corpus-loader", repo_root).load_corpus(repo_root)
    ctx = _Ctx(repo_root, corpus, judge)
    for rule in _RULES:
        rule(ctx)
    findings = ctx.findings
    for slug in ("citation-checker", "size-checker"):
        for item in _load_dep(slug, repo_root).check(repo_root):
            findings.append(Finding(
                _g(item, "rule_id"), _g(item, "severity"), _g(item, "file"),
                _g(item, "line"), _g(item, "message"),
            ))
    if paths is not None:
        roots = [(Path(p) if Path(p).is_absolute() else repo_root / p).resolve() for p in paths]

        def within(f):
            target = (repo_root / f.file).resolve()
            return any(target == r or r in target.parents for r in roots)

        findings = [f for f in findings if within(f)]
    return LintReport(findings, strict)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

USAGE = "usage: hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]"


def _usage(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    fmt = "text"
    strict = False
    repo = None
    paths = []
    i = 0
    while i < len(args):
        arg = args[i]
        name, eq, val = arg.partition("=")
        if arg == "--strict":
            strict = True
        elif name in ("--format", "--repo-root"):
            if not eq:
                if i + 1 >= len(args):
                    return _usage(f"{name} needs a value")
                i += 1
                val = args[i]
            if name == "--format":
                if val not in ("json", "text"):
                    return _usage(f"--format must be json or text, not '{val}'")
                fmt = val
            else:
                repo = Path(val)
        elif arg.startswith("-"):
            return _usage(f"unknown argument '{arg}'")
        else:
            paths.append(Path(arg))
        i += 1
    if repo is None:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
        if out.returncode != 0:
            return _usage("not in a git repository; pass --repo-root")
        repo = Path(out.stdout.strip())
    if not repo.is_dir():
        return _usage(f"unreadable path '{repo}'")
    for p in paths:
        if not (p if p.is_absolute() else repo / p).exists():
            return _usage(f"unreadable path '{p}'")
    report = lint(paths or None, repo, strict=strict)
    if fmt == "json":
        print(json.dumps(report.to_json(), indent=2))
    else:
        for f in report.findings:
            print(f"{f.file}:{f.line}: {f.severity} {f.rule_id} {f.message}")
        print(f"{report.hard_failures} hard failure(s), {report.warnings} warning(s), "
              f"{report.skipped} skipped")
    return 1 if report.hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())
