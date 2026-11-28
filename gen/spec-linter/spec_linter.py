"""Spec linter: mechanically validates a spec corpus before anything downstream runs."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = "usage: hotdocs lint [<path>...] [--format=json|text] [--strict] [--repo-root=<dir>]"

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
_STATUSES = ("draft", "ratified", "deprecated")
_LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "builds_on")
_KINDS = ("compiled", "generated-test", "llm-judge")
_ASSET_SECTIONS = (
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
)
_RFC = re.compile(r"\b(MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)\b")
_NAME = re.compile(r"[a-z][a-z0-9-]*")

_MODS: dict = {}


# ---------------------------------------------------------------- dependencies


def _g(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _dep(repo_root, slug):
    d = Path(repo_root) / "gen" / slug
    if not d.is_dir():
        d = _tool_root() / "gen" / slug
    name = slug.replace("-", "_")
    f = d / f"{name}.py"
    pkg = None
    if not f.exists():
        f = d / name / "__init__.py"
        pkg = [str(f.parent)]
    key = (str(f.resolve()), f.stat().st_mtime_ns)
    mod = _MODS.get(key)
    if mod is None:
        spec = importlib.util.spec_from_file_location(name, f, submodule_search_locations=pkg)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        _MODS[key] = mod
    sys.modules[name] = mod
    return mod


def __getattr__(name):
    if name == "load_corpus":
        fn = _dep(_tool_root(), "corpus-loader").load_corpus
        globals()["load_corpus"] = fn
        return fn
    raise AttributeError(name)


# ---------------------------------------------------------------- report types


@dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    rationale: object = None

    def to_json(self):
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

    def _count(self, *severities):
        return sum(1 for f in self.findings if f.severity in severities)

    @property
    def hard_failures(self):
        return self._count("fail", "warn") if self.strict else self._count("fail")

    @property
    def warnings(self):
        return self._count("warn")

    @property
    def skipped(self):
        return self._count("skipped")

    def to_json(self):
        return {
            "findings": [f.to_json() for f in self.findings],
            "summary": {
                "hard_failures": self.hard_failures,
                "warnings": self.warnings,
                "skipped": self.skipped,
            },
        }


def _f(rule, file, line, message, severity="fail", rationale=None):
    return Finding(rule, severity, file, line, message, rationale)


# ---------------------------------------------------------------- corpus view


def _key_lines(lines):
    keys = {}
    if [l.strip() for l in lines[:1]] == ["---"]:
        for i, line in enumerate(lines[1:], start=2):
            if line.strip() == "---":
                break
            m = re.match(r"([A-Za-z_][\w-]*)\s*:", line)
            if m:
                keys.setdefault(m.group(1), i)
    return keys


def _section(lines, name):
    head = "## " + name
    for i, line in enumerate(lines):
        if line.rstrip() == head:
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            return i, list(range(i + 1, j))
    return None


class _D:
    def __init__(self, doc):
        self.path = Path(_g(doc, "path"))
        self.rel = str(_g(doc, "rel_path"))
        self.id = _g(doc, "doc_id")
        self.fm = _g(doc, "frontmatter") or {}
        self.body = _g(doc, "body") or ""
        self.type = _g(doc, "doc_type")
        self.has_fm = bool(_g(doc, "has_frontmatter"))
        parts = self.rel.split("/")
        self.slug = parts[2] if parts[:2] == ["specs", "components"] else None
        self.text = self.path.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()
        self.keys = _key_lines(self.lines)


class _Ctx:
    def __init__(self, corpus, repo_root, judge):
        self.root = Path(repo_root)
        self.judge = judge
        self.docs = [_D(d) for d in (_g(corpus, "docs") or [])]
        self.graph = _g(corpus, "graph")
        self.gdefs = _g(corpus, "glossary_defs") or {}
        self.gfiles = sorted(Path(p) for p in (_g(corpus, "glossary_files") or []))
        self.components = sorted(_g(corpus, "components") or {})
        self.roots = {d.id: d for d in self.of("component-root")}

    def of(self, *types):
        return [d for d in self.docs if d.type in types]

    def q(self, sql):
        return self.graph.execute(sql).fetchall()

    def where(self, cid, key):
        d = self.roots.get(cid)
        if d is None:
            return f"specs/components/{str(cid).removeprefix('comp-')}/component.md", 1
        return d.rel, d.keys.get(key, 1)

    def rel(self, p):
        return Path(os.path.relpath(Path(p).resolve(), self.root.resolve())).as_posix()

    def adapter(self, dirname, filename):
        return (self.root / "gen" / dirname / filename).exists() or (
            _tool_root() / "gen" / dirname / filename
        ).exists()


# ---------------------------------------------------------------- rules


def _r001(c):
    out = []
    for d in c.of(*_FM_TYPES):
        for k in _REQUIRED:
            if k not in d.fm:
                out.append(_f("R-LINT-001", d.rel, 1, f"missing required frontmatter field '{k}'"))
        status = d.fm.get("status")
        if status is not None and status not in _STATUSES:
            out.append(_f("R-LINT-001", d.rel, d.keys.get("status", 1),
                          f"status '{status}' is not draft, ratified or deprecated"))
        for k in _LIST_FIELDS:
            if k in d.fm and not isinstance(d.fm[k], list):
                out.append(_f("R-LINT-001", d.rel, d.keys.get(k, 1), f"{k} must be a list"))
        if "sealed" in d.fm and not isinstance(d.fm["sealed"], bool):
            out.append(_f("R-LINT-001", d.rel, d.keys.get("sealed", 1), "sealed must be a boolean"))
    return out


def _r002(c):
    out = []
    for d in c.of(*_FM_TYPES):
        if d.fm.get("status") != "ratified":
            continue
        sec = _section(d.lines, "Open questions")
        if sec and any(d.lines[i].strip() for i in sec[1]):
            out.append(_f("R-LINT-002", d.rel, sec[0] + 1,
                          "ratified spec has a non-empty Open questions section"))
        if not d.fm.get("last_ratified_commit"):
            out.append(_f("R-LINT-002", d.rel, d.keys.get("status", 1),
                          "ratified spec lacks last_ratified_commit"))
    return out


def _r003(c):
    out = []
    rows = c.q(
        "SELECT DISTINCT e.source_id, e.edge_type, e.target_id, n.id IS NULL "
        "FROM edges e LEFT JOIN nodes n ON n.id = e.target_id "
        "WHERE e.edge_type IN ('depends_on', 'realizes', 'uses_var') "
        "AND (n.id IS NULL OR n.status = 'deprecated') "
        "ORDER BY 1, 2, 3"
    )
    for src, edge_type, tgt, missing in rows:
        file, line = c.where(src, edge_type)
        why = "does not exist" if missing else "is deprecated"
        out.append(_f("R-LINT-003", file, line, f"{edge_type} references '{tgt}', which {why}"))
    # Residual native check (D13): architecture-doc depends_on.
    known = {d.id: d.fm.get("status") for d in c.docs if d.id}
    known.update({i: s for i, s in c.q("SELECT id, status FROM nodes")})
    for d in c.of("architecture"):
        deps = d.fm.get("depends_on")
        for tgt in deps if isinstance(deps, list) else []:
            line = d.keys.get("depends_on", 1)
            if tgt not in known:
                out.append(_f("R-LINT-003", d.rel, line, f"depends_on references '{tgt}', which does not exist"))
            elif known[tgt] == "deprecated":
                out.append(_f("R-LINT-003", d.rel, line, f"depends_on references '{tgt}', which is deprecated"))
    return out


def _groups(pairs):
    members: dict = {}
    for a, b in pairs:
        members.setdefault(a, set()).add(b)
    return sorted({tuple(sorted(m)) for m in members.values()})


def _r004(c):
    out = []
    pairs = c.q(
        "WITH RECURSIVE dep AS ("
        " SELECT DISTINCT source_id AS s, target_id AS t FROM edges WHERE edge_type = 'depends_on'"
        "), reach(s, t) AS ("
        " SELECT s, t FROM dep"
        " UNION"
        " SELECT r.s, d.t FROM reach r JOIN dep d ON d.s = r.t"
        ") "
        "SELECT a.s, a.t FROM reach a JOIN reach b ON a.s = b.t AND a.t = b.s"
    )
    for group in _groups(pairs):
        file, line = c.where(group[0], "depends_on")
        out.append(_f("R-LINT-004", file, line, f"depends_on cycle through {', '.join(group)}"))
    # Residual native check (D13): architecture-doc depends_on.
    arch = {d.id: d for d in c.of("architecture")}
    adj = {}
    for i, d in arch.items():
        deps = d.fm.get("depends_on")
        adj[i] = list(deps) if isinstance(deps, list) else []
    reach = {}
    for n in adj:
        seen, stack = set(), list(adj[n])
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(adj.get(x, []))
        reach[n] = seen
    arch_pairs = [(n, m) for n in adj for m in reach[n] if n in reach.get(m, ())]
    for group in _groups(arch_pairs):
        d = arch[group[0]]
        out.append(_f("R-LINT-004", d.rel, d.keys.get("depends_on", 1),
                      f"depends_on cycle through {', '.join(group)}"))
    return out


def _r005(c):
    out = []
    for d in c.of("component-root"):
        sealed = d.fm.get("sealed")
        source = d.fm.get("source_path")
        if sealed is True and not source:
            out.append(_f("R-LINT-005", d.rel, d.keys.get("sealed", 1), "sealed: true requires source_path"))
        if source and sealed is not True:
            out.append(_f("R-LINT-005", d.rel, d.keys.get("source_path", 1),
                          "source_path is set but sealed is not true"))
    return out


def _r006(c):
    return [
        _f("R-LINT-006", d.rel, d.keys.get("realizes", 1), "non-sealed component has no realizes entries")
        for d in c.of("component-root")
        if d.fm.get("sealed") is not True and not d.fm.get("realizes")
    ]


def _units(c, doc_type, prefix, rule, label):
    out = []
    pat = re.compile(prefix + r"-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}")
    seen = {}
    for d in c.of(doc_type):
        stem = d.path.stem
        if not pat.fullmatch(stem):
            out.append(_f(rule, d.rel, 1, f"{stem} is not a valid {prefix}-<comp>-NNN id"))
        elif stem in seen:
            out.append(_f(rule, d.rel, 1, f"{label} id {stem} is not unique (also {seen[stem]})"))
        seen.setdefault(stem, d.rel)
        i, head = next(((i, l) for i, l in enumerate(d.lines) if l.startswith("# ")), (0, ""))
        if head.rstrip() != f"# {stem}":
            out.append(_f(rule, d.rel, i + 1, f"{stem}'s first '# ' heading is not '# {stem}'"))
        if not _RFC.search(d.text):
            out.append(_f(rule, d.rel, 1, f"{stem} uses no RFC 2119 keyword"))
    return out


def _r007(c):
    return _units(c, "component-requirement", "R", "R-LINT-007", "requirement")


def _r017(c):
    return _units(c, "component-interface-guarantee", "G", "R-LINT-017", "guarantee")


def _r008(c):
    reqs = {d.id: d.rel for d in c.of("component-requirement")}
    rows = c.q(
        "SELECT n.id FROM nodes n WHERE n.kind = 'requirement' "
        "AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.edge_type = 'covers' AND e.target_id = n.id) "
        "ORDER BY n.id"
    )
    return [_f("R-LINT-008", reqs.get(rid, ""), 1, f"{rid} has no covering acceptance criterion")
            for (rid,) in rows]


def _covers_line(lines, start, default):
    return next((j + 1 for j in range(start, len(lines)) if "Covers:" in lines[j]), default)


def _r009(c):
    out = []
    locs = {d.id: (d.rel, _covers_line(d.lines, 0, 1)) for d in c.of("component-acceptance")}
    for d in c.of("product"):
        for i, l in enumerate(d.lines):
            m = re.match(r"###\s+(CS-[\w-]+)", l)
            if m:
                locs[m.group(1)] = (d.rel, _covers_line(d.lines, i + 1, i + 1))
    rows = c.q(
        "SELECT e.source_id, e.target_id FROM edges e WHERE e.edge_type = 'covers' "
        "AND NOT EXISTS (SELECT 1 FROM nodes n WHERE n.id = e.target_id "
        "AND n.kind IN ('requirement', 'capability')) "
        "ORDER BY 1, 2"
    )
    for src, tgt in rows:
        file, line = locs.get(src, ("", 1))
        if tgt.startswith("R-"):
            msg = f"Covers: '{tgt}' does not resolve to a real R-id"
        elif tgt.startswith("P-"):
            msg = f"Covers: '{tgt}' does not resolve to a real P-id"
        else:
            msg = f"Covers: '{tgt}' is neither an R-id nor a P-id"
        out.append(_f("R-LINT-009", file, line, msg))
    return out


def _kind_ok(line):
    m = re.match(r"Kind:(.*)$", line.strip())
    return bool(m) and m.group(1).strip().strip("`").strip() in _KINDS


def _r010(c):
    out = []
    for d in c.of("component-acceptance"):
        if not any(_kind_ok(l) for l in d.lines):
            out.append(_f("R-LINT-010", d.rel, 1,
                          f"{d.id} has no Kind: line (compiled, generated-test or llm-judge)"))
        missing = [w for w in ("Given", "When", "Then")
                   if not any(l.strip().startswith(w) for l in d.lines)]
        if missing:
            out.append(_f("R-LINT-010", d.rel, 1,
                          f"{d.id} lacks a complete Given/When/Then block (missing {', '.join(missing)})"))
    return out


def _definitions(lines):
    _, idxs = _section(lines, "Definitions") or (None, [])
    entries = []
    for i in idxs:
        m = re.match(r"- \*\*(.+?)\*\*(.*)$", lines[i])
        if m:
            entries.append((m.group(1).strip(), i + 1, [m.group(2)]))
        elif entries:
            entries[-1][2].append(lines[i])
    return [(t, ln, "\n".join(parts).lstrip("—- \t\n").strip()) for t, ln, parts in entries]


def _overlap(local, gloss):
    g = set(re.findall(r"[a-z0-9]+", gloss.lower()))
    loc = set(re.findall(r"[a-z0-9]+", local.lower()))
    return len(loc & g) / len(g) if g else 0.0


def _r011_015(c):
    out = []
    for d in c.of("component-root"):
        for term, line, text in _definitions(d.lines):
            gloss = c.gdefs.get(term.lower())
            if gloss is None:
                continue
            ratio = _overlap(text, gloss)
            if ratio >= 0.8:
                out.append(_f("R-LINT-011", d.rel, line,
                              f"Definitions entry '{term}' is a near-verbatim copy of the glossary's "
                              f"definition (overlap {ratio:.2f})"))
            elif c.judge is None:
                out.append(_f("R-LINT-015", d.rel, line,
                              f"'{term}': consistency with the glossary not judged; no model configured",
                              "skipped"))
            else:
                verdict = c.judge(term, text, gloss)
                if verdict is None:
                    out.append(_f("R-LINT-015", d.rel, line,
                                  f"'{term}': the judge could not evaluate consistency with the glossary",
                                  "skipped"))
                else:
                    conflicts, rationale = verdict
                    if conflicts:
                        out.append(_f("R-LINT-015", d.rel, line,
                                      f"Definitions entry '{term}' conflicts with the glossary's definition",
                                      "fail", rationale))
    return out


def _r013(c):
    out = []
    for d in c.of("var"):
        fields = []
        for i, l in enumerate(d.lines):
            m = re.match(r"\s*[-*]\s+(.*)$", l)
            fm = m and re.match(r"([A-Za-z_]+)\s*:\s*(.*)$", m.group(1).replace("`", "").replace("**", ""))
            if fm:
                fields.append((fm.group(1).lower(), fm.group(2).strip(), i + 1))
        if any(k == "sensitivity" and v == "secret" for k, v, _ in fields):
            for k, _, line in fields:
                if k in ("example", "default"):
                    out.append(_f("R-LINT-013", d.rel, line, f"secret var declaration carries {k}"))
    return out


def _r014(c):
    out = []
    split = any(re.search(r"bounded[ -]context", d.body, re.IGNORECASE) for d in c.of("architecture"))
    if len(c.gfiles) > 1 and not split:
        for g in c.gfiles:
            rel = c.rel(g)
            if rel != "specs/glossary.md":
                out.append(_f("R-LINT-014", rel, 1,
                              f"{rel} is a second glossary-like file with no architecture-level "
                              "bounded-context split decision"))
    return out


def _r016(c):
    return [_f("R-LINT-016", d.rel, 1, "unit file carries a frontmatter block")
            for d in c.of(*_UNIT_TYPES) if d.has_fm]


def _r018(c):
    out = []
    rows = c.q(
        "SELECT DISTINCT e.source_id, e.target_id, n.owner_component_id, n.id IS NULL, "
        "EXISTS (SELECT 1 FROM edges d WHERE d.edge_type = 'depends_on' "
        "AND d.source_id = e.source_id AND d.target_id = n.owner_component_id) "
        "FROM edges e LEFT JOIN nodes n ON n.id = e.target_id AND n.kind = 'guarantee' "
        "WHERE e.edge_type = 'depends_on_guarantees' "
        "ORDER BY 1, 2"
    )
    for src, tgt, owner, missing, listed in rows:
        file, line = c.where(src, "depends_on_guarantees")
        if missing:
            out.append(_f("R-LINT-018", file, line,
                          f"depends_on_guarantees references '{tgt}', which does not exist"))
        elif not listed:
            out.append(_f("R-LINT-018", file, line,
                          f"depends_on_guarantees references '{tgt}', owned by {owner}, "
                          "which depends_on does not list"))
    return out


def _r019(c):
    out = []
    files = {d.rel: d.lines for d in c.docs}
    for g in c.gfiles:
        files.setdefault(c.rel(g), g.read_text(encoding="utf-8").splitlines())
    for rel in sorted(files):
        for i, line in enumerate(files[rel]):
            if line != line.rstrip():
                out.append(_f("R-LINT-019", rel, i + 1, "line ends in trailing whitespace"))
    return out


def _r024(c):
    out = []
    for d in c.of("component-root"):
        _, idxs = _section(d.lines, "Purpose") or (None, [])
        for i in idxs:
            for m in re.finditer(r"\bD\d+\b", d.lines[i]):
                out.append(_f("R-LINT-024", d.rel, i + 1,
                              f"Purpose cites decision id {m.group(0)}; Purpose must be dependent-safe"))
    return out


def _r031(c):
    out = []
    covered = {t for (t,) in c.q("SELECT DISTINCT target_id FROM edges WHERE edge_type = 'covers'")}
    reqs = c.of("component-requirement")
    for cli in c.of("component-interface-cli"):
        own = [r for r in reqs if r.slug == cli.slug]
        if not any("interface/cli.md" in r.text and r.id in covered for r in own):
            out.append(_f("R-LINT-031", cli.rel, 1,
                          f"comp-{cli.slug}: no requirement citing interface/cli.md is covered by a "
                          "criterion (specs/architecture/acceptance-criteria.md)", "warn"))
    return out


def _r032(c):
    out = []
    if (c.root / ".hotdocs-tool.json").exists():
        tool_gen = _tool_root() / "gen"
        for name in c.components:
            if (tool_gen / name).is_dir():
                out.append(_f("R-LINT-032", f"specs/components/{name}/component.md", 1,
                              f"component '{name}' would shadow the tool's gen/{name}/ (D199)"))
    return out


def _r034(c):
    out = []
    for d in c.of("component-root"):
        if "assets" not in d.fm:
            continue
        line = d.keys.get("assets", 1)

        def add(msg, _d=d, _line=line):
            out.append(_f("R-LINT-034", _d.rel, _line, msg))

        assets = d.fm["assets"]
        if not isinstance(assets, list):
            add("assets must be a list of <kind>:<path> strings")
            continue
        deps = d.fm.get("depends_on") or []
        done = set()
        for e in assets:
            kind, sep, path = e.partition(":")
            if not sep or not _NAME.fullmatch(kind) or not path:
                add(f"asset '{e}' is not <kind>:<path>")
                continue
            if path.startswith("/") or "\\" in path:
                add(f"asset '{e}': path must be relative with / separators")
            if ".." in path.split("/"):
                add(f"asset '{e}': path contains ..")
            if path.endswith(".py"):
                add(f"asset '{e}': path ends in .py")
            if kind == "python":
                add(f"asset '{e}': python is never declared")
                continue
            if kind in done:
                continue
            done.add(kind)
            defn = c.root / "specs" / "architecture" / f"asset-kind-{kind}.md"
            if not defn.exists():
                if not c.adapter(f"kind-{kind}", f"kind_{kind.replace('-', '_')}.py"):
                    add(f"asset kind '{kind}' has no definition; run hotdocs kind new {kind}")
                continue
            lines = defn.read_text(encoding="utf-8").splitlines()
            for name in _ASSET_SECTIONS:
                sec = _section(lines, name)
                if sec is None:
                    add(f"asset kind '{kind}' definition lacks section '{name}'")
                elif not any(lines[i].strip() for i in sec[1]):
                    add(f"asset kind '{kind}' definition has empty section '{name}'")
            if f"comp-kind-{kind}" not in deps:
                add(f"asset kind '{kind}' is defined in this repository; "
                    f"depends_on must list comp-kind-{kind}")
    return out


def _r036(c):
    out = []
    for d in c.of("component-root", "product"):
        if "drivers" not in d.fm:
            continue
        line = d.keys.get("drivers", 1)

        def add(msg, _d=d, _line=line):
            out.append(_f("R-LINT-036", _d.rel, _line, msg))

        items = d.fm["drivers"]
        if not isinstance(items, list):
            add("drivers must be one line: [a, b]")
            continue
        deps = d.fm.get("depends_on") or []
        for item in items:
            if not _NAME.fullmatch(item):
                add(f"driver '{item}' is not a driver name")
                continue
            defined = (c.root / "specs" / "architecture" / f"test-driver-{item}.md").exists()
            if not defined and not c.adapter(f"driver-{item}", f"driver_{item.replace('-', '_')}.py"):
                add(f"test driver '{item}' has no definition or adapter")
            if d.type == "component-root" and defined and f"comp-driver-{item}" not in deps:
                add(f"test driver '{item}' is defined in this repository; "
                    f"depends_on must list comp-driver-{item}")
    return out


_RULES = (
    _r001, _r002, _r003, _r004, _r005, _r006, _r007, _r008, _r009, _r010,
    _r011_015, _r013, _r014, _r016, _r017, _r018, _r019, _r024, _r031,
    _r032, _r034, _r036,
)


# ---------------------------------------------------------------- library


def _prefixes(paths, repo_root):
    root = Path(repo_root).resolve()
    return [Path(os.path.relpath((root / Path(p)).resolve(), root)).as_posix() for p in paths]


def _keep(file, prefixes):
    return any(pre == "." or file == pre or file.startswith(pre + "/") for pre in prefixes)


def lint(paths, repo_root, strict=False, judge=None):
    repo_root = Path(repo_root)
    corpus = _dep(repo_root, "corpus-loader").load_corpus(repo_root)
    ctx = _Ctx(corpus, repo_root, judge)
    findings = []
    for rule in _RULES:
        findings.extend(rule(ctx))
    for slug in ("citation-checker", "size-checker"):
        for f in _dep(repo_root, slug).check(repo_root) or []:
            findings.append(Finding(
                _g(f, "rule_id"),
                _g(f, "severity"),
                str(_g(f, "file")),
                _g(f, "line"),
                _g(f, "message"),
                _g(f, "rationale"),
            ))
    if paths is not None:
        pre = _prefixes(paths, repo_root)
        findings = [f for f in findings if _keep(f.file, pre)]
    return LintReport(findings, strict)


# ---------------------------------------------------------------- CLI


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _git_root():
    cwd = Path.cwd().resolve()
    return next((d for d in (cwd, *cwd.parents) if (d / ".git").exists()), None)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    fmt, strict, root, paths = "text", False, None, []
    i = 0
    while i < len(args):
        a = args[i]
        name, eq, val = a.partition("=")
        if name in ("--format", "--repo-root"):
            if not eq:
                i += 1
                if i == len(args):
                    return _usage_error(f"{name} needs a value")
                val = args[i]
            if name == "--format":
                fmt = val
            else:
                root = val
        elif a == "--strict":
            strict = True
        elif a.startswith("-"):
            return _usage_error(f"unknown argument {a}")
        else:
            paths.append(a)
        i += 1
    if fmt not in ("json", "text"):
        return _usage_error(f"--format must be json or text, not '{fmt}'")
    repo = Path(root) if root is not None else _git_root()
    if repo is None:
        return _usage_error("not inside a git repository; pass --repo-root")
    if not repo.is_dir():
        return _usage_error(f"cannot read {repo}")
    for p in paths:
        if not (repo / p).exists():
            return _usage_error(f"cannot read {p}")
    report = lint([Path(p) for p in paths] or None, repo, strict=strict)
    if fmt == "json":
        print(json.dumps(report.to_json(), indent=2))
    else:
        for f in report.findings:
            print(f"{f.file}:{f.line}: {f.severity} {f.rule_id}: {f.message}")
        print(f"{report.hard_failures} hard failure(s), {report.warnings} warning(s), "
              f"{report.skipped} skipped")
    return 1 if report.hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
