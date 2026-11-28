"""Spec linter: mechanically validates a spec corpus before anything downstream runs."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve()
_TOOL_ROOT = next((p.parent for p in _HERE.parents if p.name == "gen"), _HERE.parent)
_LOADED: dict = {}


def _load_module(base: Path, slug: str, mod: str):
    """Load a dependency by path: <base>/gen/<slug>/, else <tool_root>/gen/<slug>/."""
    d = Path(base) / "gen" / slug
    if not d.is_dir():
        d = _TOOL_ROOT / "gen" / slug
    file = d / f"{mod}.py"
    search = None
    if not file.is_file():
        file = d / mod / "__init__.py"
        search = [str(d / mod)]
    key = str(file.resolve())
    module = _LOADED.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(mod, file, submodule_search_locations=search)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod] = module
        spec.loader.exec_module(module)
        _LOADED[key] = module
    sys.modules[mod] = module
    return module


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


load_corpus = _get(_load_module(_TOOL_ROOT, "corpus-loader", "corpus_loader"), "load_corpus")


@dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    rationale: object = None

    def to_json(self) -> dict:
        d = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }
        if self.rationale is not None:
            d["rationale"] = self.rationale
        return d


@dataclass
class LintReport:
    findings: list = field(default_factory=list)
    strict: bool = False

    @property
    def hard_failures(self) -> int:
        counted = ("fail", "warn") if self.strict else ("fail",)
        return sum(f.severity in counted for f in self.findings)

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


# ---------------------------------------------------------------- helpers

_FM_TYPES = ("component-root", "product", "architecture", "var", "decision")
_LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "builds_on")
_RFC = re.compile(r"\b(MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)\b")
_KIND = re.compile(r"^Kind:\s*(compiled|generated-test|llm-judge)$")
_ENTRY = re.compile(r"^-\s+\*\*(.+?)\*\*(.*)$")
_BULLET = re.compile(r"^\s*[-*]\s+[`*]*([A-Za-z_]+)[`*]*\s*:\s*(.*)$")
_NAME = re.compile(r"[a-z][a-z0-9-]*")
_SECTIONS = (
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
)


def _fm(d) -> dict:
    return _get(d, "frontmatter") or {}


def _rel(d) -> str:
    return _get(d, "rel_path")


def _type(d) -> str:
    return _get(d, "doc_type")


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _slug(cid) -> str:
    cid = cid or ""
    return cid[5:] if cid.startswith("comp-") else cid


def _fm_end(lines) -> int:
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i
    return 0


def _key_line(lines, key) -> int:
    for i, line in enumerate(lines[1:_fm_end(lines)], start=2):
        if line.startswith(key + ":"):
            return i
    return 1


def _section(lines, name):
    """(heading line number, [(line number, text), ...]) up to the next `## ` line, or None."""
    for i, line in enumerate(lines):
        if line.strip() == f"## {name}":
            body = []
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    break
                body.append((j + 1, lines[j]))
            return i + 1, body
    return None


def _adapter_exists(ctx, prefix: str, name: str) -> bool:
    rel = Path("gen") / f"{prefix}-{name}" / f"{prefix}_{name.replace('-', '_')}.py"
    return (ctx.repo_root / rel).is_file() or (_TOOL_ROOT / rel).is_file()


def _cycle_groups(pairs) -> list:
    groups: dict = {}
    for a, b in pairs:
        groups.setdefault(a, set()).add(b)
    return sorted({tuple(sorted(g)) for g in groups.values()})


class _Ctx:
    def __init__(self, repo_root: Path, corpus, judge, paths):
        self.repo_root = repo_root
        self.judge = judge
        self.con = _get(corpus, "graph")
        self.glossary_defs = _get(corpus, "glossary_defs") or {}
        self.glossary_files = _get(corpus, "glossary_files") or []
        comps_dir = repo_root / "specs" / "components"
        self.orphans = sorted(
            d.name
            for d in comps_dir.glob("*")
            if d.is_dir()
            and not (d / "component.md").is_file()
            and any(f.is_file() for f in d.rglob("*"))
        )
        self.prefixes = tuple(f"specs/components/{n}/" for n in self.orphans)
        self.docs = [d for d in (_get(corpus, "docs") or []) if not _rel(d).startswith(self.prefixes)]
        self.components = [
            (name, c)
            for name, c in sorted((_get(corpus, "components") or {}).items())
            if name not in self.orphans and _get(c, "root") is not None
        ]
        self.doc_by_id = {_get(d, "doc_id"): d for d in self.docs if _type(d) in _FM_TYPES}
        self.paths = None if paths is None else [
            (Path(p) if Path(p).is_absolute() else repo_root / p).resolve() for p in paths
        ]
        self._lines: dict = {}

    def lines(self, rel: str) -> list:
        if rel not in self._lines:
            self._lines[rel] = (self.repo_root / rel).read_text(encoding="utf-8").splitlines()
        return self._lines[rel]

    def query(self, sql: str) -> list:
        return self.con.execute(sql).fetchall()

    def keep(self, f: Finding) -> bool:
        if f.rule_id != "R-LINT-037" and str(f.file).startswith(self.prefixes):
            return False
        if self.paths is None:
            return True
        target = (self.repo_root / f.file).resolve()
        return any(target == p or p in target.parents for p in self.paths)


# ---------------------------------------------------------------- rules


def _rule_001(ctx):
    out = []
    for d in ctx.docs:
        if _type(d) not in _FM_TYPES:
            continue
        rel, fm = _rel(d), _fm(d)
        lines = ctx.lines(rel)
        for key in ("id", "title", "status", "owners"):
            if key not in fm:
                out.append(Finding("R-LINT-001", "fail", rel, 1, f"frontmatter lacks required field '{key}'"))
        for key in _LIST_FIELDS:
            if key in fm and not isinstance(fm[key], list):
                out.append(Finding("R-LINT-001", "fail", rel, _key_line(lines, key),
                                   f"frontmatter field '{key}' must be a list"))
        if "sealed" in fm and not isinstance(fm["sealed"], bool):
            out.append(Finding("R-LINT-001", "fail", rel, _key_line(lines, "sealed"),
                               "frontmatter field 'sealed' must be a boolean"))
    return out


def _rule_002(ctx):
    out = []
    for d in ctx.docs:
        fm = _fm(d)
        if _type(d) not in _FM_TYPES or fm.get("status") != "ratified":
            continue
        rel = _rel(d)
        lines = ctx.lines(rel)
        sec = _section(lines, "Open questions")
        if sec and any(t.strip() for _, t in sec[1]):
            out.append(Finding("R-LINT-002", "fail", rel, sec[0],
                               "status is ratified but the Open questions section is not empty"))
        if not fm.get("last_ratified_commit"):
            out.append(Finding("R-LINT-002", "fail", rel, _key_line(lines, "status"),
                               "status is ratified but last_ratified_commit is missing"))
    return out


def _rule_003(ctx):
    out = []
    status = {
        nid: dep
        for nid, dep in ctx.query(
            "SELECT id, bool_or(coalesce(status, '') = 'deprecated') FROM nodes GROUP BY id"
        )
    }

    def problem(tgt):
        if tgt in status:
            dep = status[tgt]
        elif tgt in ctx.doc_by_id:
            dep = _fm(ctx.doc_by_id[tgt]).get("status") == "deprecated"
        else:
            return "does not exist"
        return "is deprecated" if dep else None

    rows = [
        (ctx.doc_by_id[src], etype, tgt)
        for src, etype, tgt in ctx.query(
            "SELECT DISTINCT source_id, edge_type, target_id FROM edges "
            "WHERE edge_type IN ('depends_on', 'realizes', 'uses_var') "
            "ORDER BY source_id, edge_type, target_id"
        )
    ]
    # D13 residual: architecture-doc depends_on is not in nodes/edges.
    rows += [
        (d, "depends_on", t)
        for d in ctx.docs
        if _type(d) == "architecture"
        for t in _as_list(_fm(d).get("depends_on"))
    ]
    for doc, etype, tgt in rows:
        p = problem(tgt)
        if p:
            rel = _rel(doc)
            out.append(Finding("R-LINT-003", "fail", rel, _key_line(ctx.lines(rel), etype),
                               f"{etype} references '{tgt}', which {p}"))
    return out


def _rule_004(ctx):
    out = []
    pairs = ctx.query(
        """
        WITH RECURSIVE dep AS (
            SELECT DISTINCT source_id AS s, target_id AS t FROM edges WHERE edge_type = 'depends_on'
        ),
        reach(s, t) AS (
            SELECT s, t FROM dep
            UNION
            SELECT r.s, d.t FROM reach r JOIN dep d ON r.t = d.s
        )
        SELECT a.s, a.t FROM reach a JOIN reach b ON a.s = b.t AND a.t = b.s
        ORDER BY a.s, a.t
        """
    )
    groups = _cycle_groups(pairs)
    # D13 residual: cycles among architecture docs' depends_on.
    arch = {_get(d, "doc_id"): d for d in ctx.docs if _type(d) == "architecture"}
    adj = {a: [t for t in _as_list(_fm(d).get("depends_on")) if t in arch] for a, d in arch.items()}
    reach = {}
    for a in adj:
        seen: set = set()
        stack = list(adj[a])
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(adj[x])
        reach[a] = seen
    groups += _cycle_groups((a, b) for a in reach for b in reach[a] if a in reach[b])
    for members in groups:
        rel = _rel(ctx.doc_by_id[members[0]])
        out.append(Finding("R-LINT-004", "fail", rel, _key_line(ctx.lines(rel), "depends_on"),
                           f"depends_on cycle through {', '.join(members)}"))
    return out


def _rule_005(ctx):
    out = []
    for _, c in ctx.components:
        root = _get(c, "root")
        rel, fm = _rel(root), _fm(root)
        lines = ctx.lines(rel)
        sealed = fm.get("sealed") is True
        if sealed and not fm.get("source_path"):
            out.append(Finding("R-LINT-005", "fail", rel, _key_line(lines, "sealed"),
                               "sealed: true but no source_path"))
        if fm.get("source_path") and not sealed:
            out.append(Finding("R-LINT-005", "fail", rel, _key_line(lines, "source_path"),
                               "source_path is set but sealed is not true"))
    return out


def _rule_006(ctx):
    out = []
    for _, c in ctx.components:
        root = _get(c, "root")
        fm = _fm(root)
        if fm.get("sealed") is not True and not fm.get("realizes"):
            out.append(Finding("R-LINT-006", "fail", _rel(root), 1,
                               "non-sealed component has no realizes entries"))
    return out


def _unit_ids(ctx, rule, subdir, prefix, what):
    out = []
    pat = re.compile(rf"^{prefix}-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{{3}}$")
    seen: dict = {}
    for name, _ in ctx.components:
        base = ctx.repo_root / "specs" / "components" / name / subdir
        for p in sorted(base.rglob("*.md")):
            if p.name == "README.md":
                continue
            rel = p.relative_to(ctx.repo_root).as_posix()
            lines = ctx.lines(rel)
            stem = p.stem
            if not pat.match(stem):
                out.append(Finding(rule, "fail", rel, 1,
                                   f"{what} file name '{stem}' is not a {prefix}-<comp>-NNN id"))
            if stem in seen:
                out.append(Finding(rule, "fail", rel, 1,
                                   f"duplicate {what} id '{stem}' (also {seen[stem]})"))
            seen.setdefault(stem, rel)
            head = next(((i + 1, l) for i, l in enumerate(lines) if l.startswith("# ")), (1, ""))
            if head[1].strip() != f"# {stem}":
                out.append(Finding(rule, "fail", rel, head[0],
                                   f"{what} heading '{head[1].strip()}' does not match file name '{stem}'"))
            if not _RFC.search("\n".join(lines)):
                out.append(Finding(rule, "fail", rel, 1, f"{what} '{stem}' uses no RFC 2119 keyword"))
    return out


def _rule_007(ctx):
    return _unit_ids(ctx, "R-LINT-007", "requirements", "R", "requirement")


def _rule_008(ctx):
    out = []
    rows = ctx.query(
        "SELECT DISTINCT n.id, n.owner_component_id FROM nodes n "
        "WHERE n.kind = 'requirement' AND NOT EXISTS ("
        "SELECT 1 FROM edges e WHERE e.edge_type = 'covers' AND e.target_id = n.id) "
        "ORDER BY n.owner_component_id, n.id"
    )
    for rid, owner in rows:
        rel = f"specs/components/{_slug(owner)}/requirements/{rid}.md"
        out.append(Finding("R-LINT-008", "fail", rel, 1, f"{rid} has no covering acceptance criterion"))
    return out


def _rule_009(ctx):
    out = []
    cs_where = {}
    for d in ctx.docs:
        if _type(d) == "product":
            for i, l in enumerate(ctx.lines(_rel(d))):
                m = re.match(r"^###\s+(CS-[A-Za-z0-9-]+)", l)
                if m:
                    cs_where.setdefault(m.group(1), (_rel(d), i + 2))
    rows = ctx.query(
        "SELECT DISTINCT e.source_id, e.target_id, s.owner_component_id FROM edges e "
        "LEFT JOIN (SELECT DISTINCT id, owner_component_id FROM nodes "
        "WHERE kind IN ('acceptance', 'capability_scenario')) s ON s.id = e.source_id "
        "WHERE e.edge_type = 'covers' AND NOT EXISTS ("
        "SELECT 1 FROM nodes t WHERE t.id = e.target_id AND t.kind IN ('requirement', 'capability')) "
        "ORDER BY e.source_id, e.target_id"
    )
    for src, tgt, owner in rows:
        if owner:
            rel = f"specs/components/{_slug(owner)}/acceptance/{src}.md"
            if rel.startswith(ctx.prefixes):
                continue
            lines = ctx.lines(rel)
            line = next((i + 1 for i, l in enumerate(lines) if "Covers:" in l), 1)
        else:
            rel, line = cs_where.get(src, ("specs/product", 1))
        if tgt.startswith("R-"):
            msg = f"Covers: '{tgt}' looks like an R-id but no such requirement exists"
        elif tgt.startswith("P-"):
            msg = f"Covers: '{tgt}' looks like a P-id but no such capability exists"
        else:
            msg = f"Covers: '{tgt}' is neither an R-id nor a P-id"
        out.append(Finding("R-LINT-009", "fail", rel, line, msg))
    return out


def _rule_010(ctx):
    out = []
    for d in ctx.docs:
        if _type(d) != "component-acceptance":
            continue
        rel, aid = _rel(d), _get(d, "doc_id")
        stripped = [l.strip() for l in ctx.lines(rel)]
        if not any(_KIND.match(s) for s in stripped):
            out.append(Finding("R-LINT-010", "fail", rel, 1,
                               f"{aid} has no Kind: line (compiled, generated-test or llm-judge)"))
        missing = [w for w in ("Given", "When", "Then") if not any(s.startswith(w) for s in stripped)]
        if missing:
            out.append(Finding("R-LINT-010", "fail", rel, 1,
                               f"{aid} lacks a complete Given/When/Then block (missing {', '.join(missing)})"))
    return out


def _glossary_entries(ctx):
    """(rel, line, term, local_text, glossary_text, overlap) for each Definitions entry naming a glossary term."""
    result = []
    for _, c in ctx.components:
        rel = _rel(_get(c, "root"))
        sec = _section(ctx.lines(rel), "Definitions")
        entries: list = []
        for lineno, text in (sec[1] if sec else []):
            m = _ENTRY.match(text)
            if m:
                entries.append([lineno, m.group(1).strip(), [m.group(2)]])
            elif entries:
                entries[-1][2].append(text)
        for lineno, term, parts in entries:
            gdef = ctx.glossary_defs.get(term.lower())
            if gdef is None:
                continue
            local = re.sub(r"^[\s—-]+", "", "\n".join(parts)).strip()
            lt = set(re.findall(r"\w+", local.lower()))
            gt = set(re.findall(r"\w+", gdef.lower()))
            result.append((rel, lineno, term, local, gdef, len(lt & gt) / max(len(gt), 1)))
    return result


def _rule_011(ctx):
    return [
        Finding("R-LINT-011", "fail", rel, line,
                f"Definitions entry '{term}' is a near-verbatim copy of the glossary's definition; "
                "record only deltas")
        for rel, line, term, _, _, ratio in _glossary_entries(ctx)
        if ratio >= 0.8
    ]


def _rule_013(ctx):
    out = []
    for d in ctx.docs:
        if _type(d) != "var":
            continue
        rel = _rel(d)
        fields: dict = {}
        for i, l in enumerate(ctx.lines(rel)):
            m = _BULLET.match(l)
            if m:
                fields.setdefault(m.group(1).lower(), (i + 1, m.group(2).strip(" `*\"'")))
        if fields.get("sensitivity", (0, ""))[1] == "secret":
            for key in ("example", "default"):
                if key in fields:
                    out.append(Finding("R-LINT-013", "fail", rel, fields[key][0],
                                       f"secret var declaration carries a '{key}' field"))
    return out


def _rule_014(ctx):
    out = []
    files = sorted(Path(p).resolve().relative_to(ctx.repo_root.resolve()).as_posix()
                   for p in ctx.glossary_files)
    split = any(
        re.search(r"bounded[ -]context", _get(d, "body") or "", re.IGNORECASE)
        for d in ctx.docs
        if _type(d) == "architecture"
    )
    if len(files) > 1 and not split:
        for rel in files:
            if rel != "specs/glossary.md":
                out.append(Finding("R-LINT-014", "fail", rel, 1,
                                   f"{rel} is a second glossary-like file with no architecture-level "
                                   "bounded-context split decision"))
    return out


def _rule_015(ctx):
    out = []
    for rel, line, term, local, gdef, ratio in _glossary_entries(ctx):
        if ratio >= 0.8:
            continue
        if ctx.judge is None:
            out.append(Finding("R-LINT-015", "skipped", rel, line,
                               f"R-LINT-015 skipped for '{term}': no model configured"))
            continue
        verdict = ctx.judge(term, local, gdef)
        if verdict is None:
            out.append(Finding("R-LINT-015", "skipped", rel, line,
                               f"R-LINT-015 skipped for '{term}': the judge could not judge"))
        elif verdict[0]:
            out.append(Finding("R-LINT-015", "fail", rel, line,
                               f"Definitions entry '{term}' conflicts with the glossary's definition",
                               verdict[1]))
    return out


def _rule_016(ctx):
    out = []
    for name, _ in ctx.components:
        base = ctx.repo_root / "specs" / "components" / name
        files = [p for sub in ("requirements", "interface", "acceptance") for p in sorted((base / sub).rglob("*.md"))]
        files += [p for p in [base / "constraints.md"] if p.is_file()]
        for p in files:
            if p.name == "README.md":
                continue
            rel = p.relative_to(ctx.repo_root).as_posix()
            if _fm_end(ctx.lines(rel)):
                out.append(Finding("R-LINT-016", "fail", rel, 1,
                                   "unit file carries a frontmatter block; frontmatter lives only on component.md"))
    return out


def _rule_017(ctx):
    return _unit_ids(ctx, "R-LINT-017", "interface/guarantees", "G", "guarantee")


def _rule_018(ctx):
    out = []
    rows = ctx.query(
        "SELECT DISTINCT e.source_id, e.target_id, g.id, g.owner_component_id, "
        "EXISTS (SELECT 1 FROM edges d WHERE d.edge_type = 'depends_on' "
        "AND d.source_id = e.source_id AND d.target_id = g.owner_component_id) "
        "FROM edges e LEFT JOIN (SELECT DISTINCT id, owner_component_id FROM nodes "
        "WHERE kind = 'guarantee') g ON g.id = e.target_id "
        "WHERE e.edge_type = 'depends_on_guarantees' ORDER BY e.source_id, e.target_id"
    )
    for src, tgt, gid, owner, listed in rows:
        rel = _rel(ctx.doc_by_id[src])
        line = _key_line(ctx.lines(rel), "depends_on_guarantees")
        if gid is None:
            out.append(Finding("R-LINT-018", "fail", rel, line,
                               f"depends_on_guarantees references '{tgt}', which does not exist"))
        elif not listed:
            out.append(Finding("R-LINT-018", "fail", rel, line,
                               f"depends_on_guarantees references '{tgt}', owned by {owner}, "
                               "which depends_on does not list"))
    return out


def _rule_019(ctx):
    out = []
    rels = [_rel(d) for d in ctx.docs]
    rels += [r for r in ["specs/glossary.md"] if (ctx.repo_root / r).is_file()]
    for rel in sorted(rels):
        for i, l in enumerate(ctx.lines(rel)):
            if l != l.rstrip():
                out.append(Finding("R-LINT-019", "fail", rel, i + 1, "line ends in trailing whitespace"))
    return out


def _rule_024(ctx):
    out = []
    for _, c in ctx.components:
        rel = _rel(_get(c, "root"))
        sec = _section(ctx.lines(rel), "Purpose")
        for lineno, text in (sec[1] if sec else []):
            for m in re.finditer(r"\bD\d+\b", text):
                out.append(Finding("R-LINT-024", "fail", rel, lineno,
                                   f"Purpose cites decision {m.group()}; decision citations belong in Rationale"))
    return out


def _rule_031(ctx):
    out = []
    covered = {t for (t,) in ctx.query("SELECT DISTINCT target_id FROM edges WHERE edge_type = 'covers'")}
    for name, c in ctx.components:
        cli = _get(c, "interface_cli")
        if cli is None:
            continue
        reqs = _get(c, "requirements") or {}
        ok = any("interface/cli.md" in (_get(r, "body") or "") and rid in covered for rid, r in reqs.items())
        if not ok:
            out.append(Finding("R-LINT-031", "warn", _rel(cli), 1,
                               f"comp-{name} has interface/cli.md, but no requirement citing interface/cli.md "
                               "is covered by a criterion (specs/architecture/acceptance-criteria.md)"))
    return out


def _rule_032(ctx):
    out = []
    if (ctx.repo_root / ".hotdocs-tool.json").is_file():
        for name, c in ctx.components:
            if (_TOOL_ROOT / "gen" / name).is_dir():
                out.append(Finding("R-LINT-032", "fail", _rel(_get(c, "root")), 1,
                                   f"component '{name}' shadows the tool's gen/{name}/; rename it"))
    return out


def _rule_034(ctx):
    out = []
    for _, c in ctx.components:
        root = _get(c, "root")
        fm = _fm(root)
        if "assets" not in fm:
            continue
        rel = _rel(root)
        line = _key_line(ctx.lines(rel), "assets")

        def fail(msg):
            out.append(Finding("R-LINT-034", "fail", rel, line, msg))

        assets = fm["assets"]
        if not isinstance(assets, list):
            fail("assets must be a list of <kind>:<path> strings")
            continue
        deps = _as_list(fm.get("depends_on"))
        seen: set = set()
        for entry in [e for e in assets if e]:
            kind, sep, path = entry.partition(":")
            if not sep or not _NAME.fullmatch(kind) or not path:
                fail(f"asset '{entry}' is not <kind>:<path>")
                continue
            if path.startswith("/") or "\\" in path:
                fail(f"asset '{entry}': path must be relative with / separators")
            if ".." in path.split("/"):
                fail(f"asset '{entry}': path contains ..")
            if path.endswith(".py"):
                fail(f"asset '{entry}': path ends in .py")
            if kind == "python":
                fail(f"asset '{entry}': python is never declared")
                continue
            if kind in seen:
                continue
            seen.add(kind)
            definition = ctx.repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"
            if not definition.is_file() and not _adapter_exists(ctx, "kind", kind):
                fail(f"asset kind '{kind}' has no definition; run hotdocs kind new {kind}")
            if definition.is_file():
                dlines = definition.read_text(encoding="utf-8").splitlines()
                for name in _SECTIONS:
                    sec = _section(dlines, name)
                    if sec is None:
                        fail(f"asset kind '{kind}' definition lacks section '{name}'")
                    elif not any(t.strip() for _, t in sec[1]):
                        fail(f"asset kind '{kind}' definition has empty section '{name}'")
                if f"comp-kind-{kind}" not in deps:
                    fail(f"asset kind '{kind}' is defined in this repository; "
                         f"depends_on must list comp-kind-{kind}")
    return out


def _rule_036(ctx):
    out = []
    for d in ctx.docs:
        fm = _fm(d)
        if _type(d) not in ("component-root", "product") or "drivers" not in fm:
            continue
        rel = _rel(d)
        line = _key_line(ctx.lines(rel), "drivers")

        def fail(msg):
            out.append(Finding("R-LINT-036", "fail", rel, line, msg))

        items = fm["drivers"]
        if not isinstance(items, list):
            fail("drivers must be one line: [a, b]")
            continue
        deps = _as_list(fm.get("depends_on"))
        for item in [i for i in items if i]:
            if not _NAME.fullmatch(item):
                fail(f"driver '{item}' is not a driver name")
                continue
            definition = ctx.repo_root / "specs" / "architecture" / f"test-driver-{item}.md"
            if not definition.is_file() and not _adapter_exists(ctx, "driver", item):
                fail(f"test driver '{item}' has no definition or adapter")
            if _type(d) == "component-root" and definition.is_file() and f"comp-driver-{item}" not in deps:
                fail(f"test driver '{item}' is defined in this repository; "
                     f"depends_on must list comp-driver-{item}")
    return out


def _rule_037(ctx):
    return [
        Finding("R-LINT-037", "fail", f"specs/components/{name}/", 1,
                f"specs/components/{name}/ has no component.md")
        for name in ctx.orphans
    ]


_RULES = (
    _rule_001, _rule_002, _rule_003, _rule_004, _rule_005, _rule_006, _rule_007,
    _rule_008, _rule_009, _rule_010, _rule_011, _rule_013, _rule_014, _rule_015,
    _rule_016, _rule_017, _rule_018, _rule_019, _rule_024, _rule_031, _rule_032,
    _rule_034, _rule_036, _rule_037,
)


def lint(paths, repo_root: Path, strict: bool = False, judge=None) -> LintReport:
    repo_root = Path(repo_root)
    loader = _load_module(repo_root, "corpus-loader", "corpus_loader")
    corpus = _get(loader, "load_corpus")(repo_root)
    ctx = _Ctx(repo_root, corpus, judge, paths)
    findings = []
    for rule in _RULES:
        findings.extend(rule(ctx))
    for slug, mod in (("citation-checker", "citation_checker"), ("size-checker", "size_checker")):
        for item in _get(_load_module(repo_root, slug, mod), "check")(repo_root):
            findings.append(Finding(_get(item, "rule_id"), _get(item, "severity"), _get(item, "file"),
                                    _get(item, "line"), _get(item, "message")))
    return LintReport([f for f in findings if ctx.keep(f)], strict)


# ---------------------------------------------------------------- CLI

USAGE = "usage: hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]"


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _git_root(start: Path) -> Path:
    return next((p for p in (start, *start.parents) if (p / ".git").exists()), start)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    fmt, strict, repo_root, paths = "text", False, None, []
    i = 0
    while i < len(args):
        tok = args[i]
        i += 1
        name, eq, value = tok.partition("=")
        if name in ("--format", "--repo-root"):
            if not eq:
                if i >= len(args):
                    return _usage_error(f"{name} needs a value")
                value = args[i]
                i += 1
            if name == "--format":
                if value not in ("json", "text"):
                    return _usage_error(f"--format must be json or text, not {value!r}")
                fmt = value
            else:
                repo_root = Path(value)
        elif tok == "--strict":
            strict = True
        elif tok.startswith("-"):
            return _usage_error(f"unknown argument {tok!r}")
        else:
            paths.append(Path(tok))
    if repo_root is None:
        repo_root = _git_root(Path.cwd())
    for p in paths:
        if not (repo_root / p).exists():
            return _usage_error(f"cannot read path {str(p)!r}")
    report = lint(paths or None, repo_root, strict=strict)
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
