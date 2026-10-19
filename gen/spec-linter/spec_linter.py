"""
spec-linter — bootstrap implementation.

HAND-AUTHORED BOOTSTRAP. This pipeline's own `generator` component does not
exist yet, so there is no agentic cold-regen pipeline to have produced this
file the normal way. A human/agent stood in for `generator` exactly once to
validate that `specs/components/spec-linter/` is sufficient to implement
from. See `.provenance.json` alongside this file and
`verification/spec-linter/BOOTSTRAP.md` for the honest account of what was
bootstrapped, what was ambiguous, and what was decided unilaterally.

Implements all nineteen R-LINT-* requirements from
`specs/components/spec-linter/requirements/`, matching the CLI and
`LintReport` contract in `specs/components/spec-linter/interface/` exactly.

REWRITTEN for D15 (one-file-per-unit component layout): a component is no
longer four flat files (`spec.md`/`interface.md`/`acceptance.md`/
`constraints.md`) parsed by regex into sub-sections — it's `component.md`
(root) plus `requirements/`, `interface/` (+ `interface/data/`), and
`acceptance/` directories, each holding one file per addressable unit, plus
`constraints.md` staying flat. This rewrite replaces block-boundary regex
parsing (`_requirement_blocks`, `CRITERION_HEADER_RE`-over-one-shared-file)
with directory listing wherever D15 made that possible — removing a whole
class of parsing bug by construction, not just by convention. Product
capabilities (`specs/product/`) are unaffected by D15 and keep their
original one-file-with-inline-scenarios shape; `rule_criterion_wellformed`
still branches on that.

EXTENDED for D16 (behavioral guarantees + opt-in blast-radius narrowing):
`interface/` gained a fourth kind, `interface/guarantees/G-<comp>-NNN.md`
(R-LINT-017, mirroring R-LINT-007's requirement-identity check exactly),
and a new frontmatter field, `depends_on_guarantees`, got its own
reference-resolution rule (R-LINT-018) distinct from R-LINT-003's, because
a `G-id` resolves against `Component.interface_guarantees`, never
`id_index` — the same separation R-ids/AC-ids already had.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# RFC 2119 keyword set.
#
# Open question in spec originally asked: full RFC 2119 set, or the curated
# subset this project actually uses? Resolved by cross-referencing
# SPEC_GUIDELINES.md itself, which opens by declaring: "Keywords MUST, MUST
# NOT, SHOULD, SHOULD NOT, and MAY are used per RFC 2119." That sentence
# already answers this open question directly. Flagged in the bootstrap
# report.
# ---------------------------------------------------------------------------
RFC2119_KEYWORDS = ("MUST NOT", "MUST", "SHOULD NOT", "SHOULD", "MAY")

SEVERITY_FAIL = "fail"
SEVERITY_WARN = "warn"
SEVERITY_SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    rationale: str | None = None  # present only for llm-judge findings that actually ran

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
    findings: list[Finding] = field(default_factory=list)

    @property
    def hard_failures(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_FAIL)

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_WARN)

    @property
    def skipped(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_SKIPPED)

    def to_json(self) -> dict:
        return {
            "findings": [f.to_json() for f in self.findings],
            "summary": {
                "hard_failures": self.hard_failures,
                "warnings": self.warnings,
                "skipped": self.skipped,
            },
        }

    def to_text(self) -> str:
        if not self.findings:
            return "spec-linter: no findings\n"
        lines = []
        for f in self.findings:
            lines.append(f"[{f.severity.upper():4}] {f.file}:{f.line} {f.rule_id} — {f.message}")
        lines.append("")
        lines.append(f"{self.hard_failures} failure(s), {self.warnings} warning(s), "
                      f"{self.skipped} skipped")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Corpus model
# ---------------------------------------------------------------------------

# Doc types we actually lint. README.md placeholders under specs/ are
# scaffolding/documentation, not governed specs — SPEC_GUIDELINES.md §1
# states this explicitly, and the D15 governed set for a component is:
# component.md, everything under requirements/ and interface/ (including
# interface/data/) and acceptance/, and constraints.md.

REQUIREMENT_FILE_RE = re.compile(r"^(R-[A-Z0-9]+-\d+)\.md$")
ACCEPTANCE_FILE_RE = re.compile(r"^(AC-[A-Z0-9]+-\d+[a-z]?)\.md$")
GUARANTEE_FILE_RE = re.compile(r"^(G-[A-Z0-9]+-\d+)\.md$")
COVERS_RE = re.compile(r"^Covers:\s*(\S+)", re.MULTILINE)
KIND_RE = re.compile(r"^Kind:\s*(\S+)", re.MULTILINE)
GHERKIN_BLOCK_RE = re.compile(r"```gherkin\n(.*?)```", re.DOTALL)
CRITERION_HEADER_RE = re.compile(r"^###\s+(\S+)\s*$", re.MULTILINE)  # product capabilities only
GLOSSARY_TERM_RE = re.compile(r"^-\s+\*\*([^*]+)\*\*", re.MULTILINE)
# Captures a glossary bullet's full text (term + definition, up to the next
# top-level bullet or end of section) so R-LINT-011/015 can compare content,
# not just term names.
GLOSSARY_ENTRY_RE = re.compile(r"^-\s+\*\*([^*]+)\*\*(.*?)(?=^-\s+\*\*|\Z)",
                                re.MULTILINE | re.DOTALL)
WORD_RE = re.compile(r"[a-z0-9']+")
REQ_ID_HEADER_RE = re.compile(r"^#\s+(R-[A-Z0-9]+-\d+)\s*$", re.MULTILINE)
AC_ID_HEADER_RE = re.compile(r"^#\s+(AC-[A-Z0-9]+-\d+[a-z]?)\s*$", re.MULTILINE)
GUARANTEE_ID_HEADER_RE = re.compile(r"^#\s+(G-[A-Z0-9]+-\d+)\s*$", re.MULTILINE)


@dataclass
class Doc:
    path: Path
    rel_path: str
    doc_id: str | None
    frontmatter: dict
    body: str
    doc_type: str
    # "component-root" | "component-requirement" | "component-interface-cli" |
    # "component-interface-library" | "component-interface-data" |
    # "component-acceptance" | "component-constraints" | "product" | "var" |
    # "architecture" | "decision"
    component: str | None = None  # component directory name, if applicable
    has_frontmatter: bool = False  # True if a --- block was found, regardless of content


@dataclass
class Component:
    name: str
    root: Doc | None
    requirements: dict[str, Doc]
    interface_cli: Doc | None
    interface_library: Doc | None
    interface_data: dict[str, Doc]
    interface_guarantees: dict[str, Doc]
    acceptance: dict[str, Doc]
    constraints: Doc | None


@dataclass
class Corpus:
    repo_root: Path
    docs: list[Doc]
    components: dict[str, Component]
    id_index: dict[str, Doc]
    glossary_defs: dict[str, str]  # lowercased term -> its definition text
    glossary_files: list[Path]

    @property
    def glossary_terms(self) -> set[str]:
        return set(self.glossary_defs)


def _parse_frontmatter(text: str) -> tuple[dict, str, bool]:
    """Minimal frontmatter parser: flat `key: value` / `key: [a, b]` pairs.

    No PyYAML dependency — every frontmatter block observed in this corpus is
    a flat scalar/inline-list block, so a small hand-rolled parser keeps the
    bootstrap runnable with zero external packages.

    Returns (frontmatter_dict, body_text, had_frontmatter_block).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    fm: dict = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                fm[key] = [] if not inner else [v.strip() for v in inner.split(",")]
            elif value.lower() in ("true", "false"):
                fm[key] = value.lower() == "true"
            else:
                fm[key] = value.strip('"').strip("'")
        i += 1
    body = "\n".join(lines[i + 1:]) if i < len(lines) else ""
    return fm, body, True


def _classify(rel_path: str) -> tuple[str | None, str | None]:
    """Returns (doc_type, component_name) or (None, None) if not a governed spec."""
    parts = rel_path.split("/")
    if rel_path == "specs/glossary.md":
        return "glossary", None
    if len(parts) >= 3 and parts[0] == "specs" and parts[1] == "components":
        component = parts[2]
        rest = parts[3:]
        if rest == ["component.md"]:
            return "component-root", component
        if len(rest) == 2 and rest[0] == "requirements" and REQUIREMENT_FILE_RE.match(rest[1]):
            return "component-requirement", component
        if len(rest) == 2 and rest[0] == "interface" and rest[1] == "cli.md":
            return "component-interface-cli", component
        if len(rest) == 2 and rest[0] == "interface" and rest[1] == "library.md":
            return "component-interface-library", component
        if len(rest) == 3 and rest[0] == "interface" and rest[1] == "data":
            return "component-interface-data", component
        if (len(rest) == 3 and rest[0] == "interface" and rest[1] == "guarantees"
                and GUARANTEE_FILE_RE.match(rest[2])):
            return "component-interface-guarantee", component
        if len(rest) == 2 and rest[0] == "acceptance" and ACCEPTANCE_FILE_RE.match(rest[1]):
            return "component-acceptance", component
        if rest == ["constraints.md"]:
            return "component-constraints", component
        return None, None  # README.md, a stray file, etc. — not governed
    if len(parts) == 3 and parts[0] == "specs" and parts[1] == "product":
        return (None, None) if parts[2] == "README.md" else ("product", None)
    if len(parts) == 3 and parts[0] == "specs" and parts[1] == "architecture":
        return (None, None) if parts[2] == "README.md" else ("architecture", None)
    if len(parts) == 3 and parts[0] == "specs" and parts[1] == "vars":
        return (None, None) if parts[2] == "README.md" else ("var", None)
    if len(parts) == 3 and parts[0] == "specs" and parts[1] == "decisions":
        return (None, None) if parts[2] == "README.md" else ("decision", None)
    return None, None


def load_corpus(repo_root: Path) -> Corpus:
    specs_dir = repo_root / "specs"
    docs: list[Doc] = []
    id_index: dict[str, Doc] = {}
    glossary_defs: dict[str, str] = {}
    glossary_files: list[Path] = []
    components: dict[str, Component] = {}

    def get_component(name: str) -> Component:
        return components.setdefault(
            name,
            Component(name=name, root=None, requirements={}, interface_cli=None,
                      interface_library=None, interface_data={}, interface_guarantees={},
                      acceptance={}, constraints=None),
        )

    for path in sorted(specs_dir.rglob("*.md")):
        rel = str(path.relative_to(repo_root))
        doc_type, component = _classify(rel)
        if doc_type is None:
            continue
        text = path.read_text(encoding="utf-8")
        if doc_type == "glossary":
            glossary_files.append(path)
            for m in GLOSSARY_ENTRY_RE.finditer(text):
                glossary_defs[m.group(1).strip().lower()] = m.group(2).strip()
            continue
        fm, body, had_fm = _parse_frontmatter(text)
        doc_id = fm.get("id")
        if doc_type in ("component-requirement", "component-acceptance", "component-interface-guarantee"):
            doc_id = path.stem

        doc = Doc(
            path=path, rel_path=rel, doc_id=doc_id, frontmatter=fm,
            body=body, doc_type=doc_type, component=component,
            has_frontmatter=had_fm,
        )
        docs.append(doc)
        if doc_id and doc_type in ("component-root", "product", "architecture", "var", "decision"):
            id_index[doc_id] = doc

        if component:
            comp = get_component(component)
            if doc_type == "component-root":
                comp.root = doc
            elif doc_type == "component-requirement":
                comp.requirements[doc_id] = doc
            elif doc_type == "component-interface-cli":
                comp.interface_cli = doc
            elif doc_type == "component-interface-library":
                comp.interface_library = doc
            elif doc_type == "component-interface-data":
                comp.interface_data[path.stem] = doc
            elif doc_type == "component-interface-guarantee":
                comp.interface_guarantees[doc_id] = doc
            elif doc_type == "component-acceptance":
                comp.acceptance[doc_id] = doc
            elif doc_type == "component-constraints":
                comp.constraints = doc

    # Also catch any stray "glossary-like" file outside the canonical path —
    # feeds R-LINT-014.
    for path in sorted(specs_dir.rglob("glossary*.md")):
        if path not in glossary_files:
            glossary_files.append(path)

    return Corpus(repo_root=repo_root, docs=docs, components=components,
                  id_index=id_index, glossary_defs=glossary_defs,
                  glossary_files=glossary_files)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def _find_line(body: str, needle: str, fallback: int = 1) -> int:
    idx = body.find(needle)
    if idx == -1:
        return fallback
    return body.count("\n", 0, idx) + 1


FRONTMATTER_BEARING_TYPES = ("component-root", "product", "architecture", "var", "decision")
UNIT_FILE_TYPES = (
    "component-requirement", "component-interface-cli", "component-interface-library",
    "component-interface-data", "component-interface-guarantee", "component-acceptance",
    "component-constraints",
)


def rule_frontmatter_completeness(corpus: Corpus) -> list[Finding]:
    """R-LINT-001 — frontmatter completeness, root-level documents only.

    Scope decision: SPEC_GUIDELINES.md §2's table conflates "unconditionally
    required" (id/title/status/owners) with "conditionally required"
    (realizes-unless-sealed, source_path-when-sealed,
    last_ratified_commit-when-ratified). Those conditionals are each covered
    by their own, more specific rule (R-LINT-002/005/006) below, so this rule
    only checks the four unconditional fields plus basic typing of whichever
    optional fields are present.

    Since D15, this only applies to frontmatter-bearing documents
    (`component-root` + product/architecture/var/decision) — unit files
    carry no frontmatter at all, and that absence is R-LINT-016's job, not
    this rule's.
    """
    findings = []
    list_fields = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "owners")
    bool_fields = ("sealed",)
    for doc in corpus.docs:
        if doc.doc_type not in FRONTMATTER_BEARING_TYPES:
            continue
        for required in ("id", "title", "status", "owners"):
            if required not in doc.frontmatter:
                findings.append(Finding("R-LINT-001", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"missing required frontmatter field '{required}'"))
        if doc.frontmatter.get("status") not in (None, "draft", "ratified", "deprecated"):
            findings.append(Finding("R-LINT-001", SEVERITY_FAIL, doc.rel_path, 1,
                                     f"status '{doc.frontmatter.get('status')}' is not one of draft|ratified|deprecated"))
        for lf in list_fields:
            if lf in doc.frontmatter and not isinstance(doc.frontmatter[lf], list):
                findings.append(Finding("R-LINT-001", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"'{lf}' must be a list"))
        for bf in bool_fields:
            if bf in doc.frontmatter and not isinstance(doc.frontmatter[bf], bool):
                findings.append(Finding("R-LINT-001", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"'{bf}' must be a boolean"))
    return findings


def rule_no_stray_frontmatter(corpus: Corpus) -> list[Finding]:
    """R-LINT-016 — a unit file (requirements/*, interface/*, acceptance/*,
    constraints.md) MUST NOT carry a frontmatter block at all (D15,
    `SPEC_GUIDELINES.md` §2's last bullet)."""
    findings = []
    for doc in corpus.docs:
        if doc.doc_type in UNIT_FILE_TYPES and doc.has_frontmatter:
            findings.append(Finding("R-LINT-016", SEVERITY_FAIL, doc.rel_path, 1,
                                     "unit file carries a frontmatter block — unit files "
                                     "carry none at all; frontmatter lives only on component.md"))
    return findings


def rule_ratified_closure(corpus: Corpus) -> list[Finding]:
    """R-LINT-002. Open questions/status live on the frontmatter-bearing
    document (component.md for a component)."""
    findings = []
    for doc in corpus.docs:
        if doc.doc_type not in FRONTMATTER_BEARING_TYPES:
            continue
        if doc.frontmatter.get("status") != "ratified":
            continue
        oq_match = re.search(r"##\s*Open questions\s*\n(.*?)(\n##|\Z)", doc.body, re.DOTALL)
        if oq_match:
            section = oq_match.group(1).strip()
            if section and section not in ("", "- None.", "None."):
                findings.append(Finding("R-LINT-002", SEVERITY_FAIL, doc.rel_path,
                                         _find_line(doc.body, "Open questions"),
                                         "status: ratified but Open questions section is non-empty"))
        if not doc.frontmatter.get("last_ratified_commit"):
            findings.append(Finding("R-LINT-002", SEVERITY_FAIL, doc.rel_path, 1,
                                     "status: ratified but last_ratified_commit is missing"))
    return findings


def rule_reference_resolution(corpus: Corpus) -> list[Finding]:
    """R-LINT-003."""
    findings = []
    for doc in corpus.docs:
        if doc.doc_type not in FRONTMATTER_BEARING_TYPES:
            continue
        for field_name in ("depends_on", "realizes", "uses_var"):
            for ref in doc.frontmatter.get(field_name, []) or []:
                target = corpus.id_index.get(ref)
                if target is None:
                    findings.append(Finding("R-LINT-003", SEVERITY_FAIL, doc.rel_path, 1,
                                             f"{field_name} references '{ref}', which does not exist"))
                elif target.frontmatter.get("status") == "deprecated":
                    findings.append(Finding("R-LINT-003", SEVERITY_FAIL, doc.rel_path, 1,
                                             f"{field_name} references '{ref}', which is deprecated"))
    return findings


def rule_depends_on_guarantees_resolution(corpus: Corpus) -> list[Finding]:
    """R-LINT-018 — `depends_on_guarantees` entries must resolve to a real
    `G-id` whose owning component is already in this component's own
    `depends_on` (D16). A stricter check than plain existence: referencing a
    guarantee of a component you don't even depend on is meaningless, not
    just unresolved — the same ownership-aware check D16 added to
    `SPEC_GUIDELINES.md` §2's rules.
    """
    findings = []
    owner_by_gid: dict[str, Component] = {
        gid: comp for comp in corpus.components.values() for gid in comp.interface_guarantees
    }
    for doc in corpus.docs:
        if doc.doc_type != "component-root":
            continue
        declared_deps = set(doc.frontmatter.get("depends_on") or [])
        for gid in doc.frontmatter.get("depends_on_guarantees", []) or []:
            owner = owner_by_gid.get(gid)
            if owner is None:
                findings.append(Finding("R-LINT-018", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"depends_on_guarantees references '{gid}', which does not exist"))
                continue
            owner_id = owner.root.doc_id if owner.root else None
            if owner_id not in declared_deps:
                findings.append(Finding(
                    "R-LINT-018", SEVERITY_FAIL, doc.rel_path, 1,
                    f"depends_on_guarantees references '{gid}' (owned by '{owner_id}'), "
                    f"but '{owner_id}' is not in this component's own depends_on"))
    return findings


def rule_acyclic_graph(corpus: Corpus) -> list[Finding]:
    """R-LINT-004 — DFS three-color cycle detection.

    Open question resolved: any correct algorithm was acceptable; this is
    the standard white/gray/black DFS marking.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {
        doc.doc_id: WHITE for doc in corpus.docs
        if doc.doc_id and doc.doc_type in FRONTMATTER_BEARING_TYPES
    }
    findings: list[Finding] = []
    reported_cycles: set[frozenset] = set()

    def edges(doc_id: str) -> list[str]:
        doc = corpus.id_index.get(doc_id)
        if not doc:
            return []
        return [d for d in (doc.frontmatter.get("depends_on") or []) if d in corpus.id_index]

    def dfs(node: str, stack: list[str]):
        color[node] = GRAY
        stack.append(node)
        for nxt in edges(node):
            if color.get(nxt) == GRAY:
                cycle = frozenset(stack[stack.index(nxt):])
                if cycle not in reported_cycles:
                    reported_cycles.add(cycle)
                    doc = corpus.id_index[node]
                    findings.append(Finding(
                        "R-LINT-004", SEVERITY_FAIL, doc.rel_path, 1,
                        f"depends_on cycle detected: {' -> '.join(stack[stack.index(nxt):] + [nxt])}",
                    ))
            elif color.get(nxt, BLACK) == WHITE:
                dfs(nxt, stack)
        stack.pop()
        color[node] = BLACK

    for doc_id in list(color):
        if color[doc_id] == WHITE:
            dfs(doc_id, [])
    return findings


def rule_sealed_consistency(corpus: Corpus) -> list[Finding]:
    """R-LINT-005 — only applies to a component's root (`component.md`)."""
    findings = []
    for doc in corpus.docs:
        if doc.doc_type != "component-root":
            continue
        sealed = doc.frontmatter.get("sealed", False)
        has_source_path = bool(doc.frontmatter.get("source_path"))
        if sealed and not has_source_path:
            findings.append(Finding("R-LINT-005", SEVERITY_FAIL, doc.rel_path, 1,
                                     "sealed: true but source_path is missing"))
        if has_source_path and not sealed:
            findings.append(Finding("R-LINT-005", SEVERITY_FAIL, doc.rel_path, 1,
                                     "source_path set but sealed is false/absent"))
    return findings


def rule_realizes_coverage(corpus: Corpus) -> list[Finding]:
    """R-LINT-006."""
    findings = []
    for doc in corpus.docs:
        if doc.doc_type != "component-root":
            continue
        if doc.frontmatter.get("sealed", False):
            continue
        if not doc.frontmatter.get("realizes"):
            findings.append(Finding("R-LINT-006", SEVERITY_FAIL, doc.rel_path, 1,
                                     "non-sealed component has zero realizes entries"))
    return findings


def rule_requirement_identity(corpus: Corpus) -> list[Finding]:
    """R-LINT-007 — since D15, one requirement per file under requirements/.
    Duplicate-id detection now reduces to "does the file's own '# R-ID'
    header match its filename" (a mismatch would mean someone copy-pasted a
    file without updating its heading) — directory listing itself already
    guarantees no two files share a name."""
    findings = []
    for comp in corpus.components.values():
        for rid, doc in comp.requirements.items():
            header_m = REQ_ID_HEADER_RE.search(doc.body)
            if header_m and header_m.group(1) != rid:
                findings.append(Finding("R-LINT-007", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"file is named {rid}.md but its own heading says "
                                         f"{header_m.group(1)}"))
            if not any(kw in doc.body for kw in RFC2119_KEYWORDS):
                findings.append(Finding("R-LINT-007", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"{rid} uses no RFC 2119 keyword ({'/'.join(RFC2119_KEYWORDS)})"))
    return findings


def rule_guarantee_identity(corpus: Corpus) -> list[Finding]:
    """R-LINT-017 — one behavioral/non-functional guarantee per file under
    `interface/guarantees/` (D16), mirroring `rule_requirement_identity`
    exactly: the file's own `# G-ID` heading must match its filename, and it
    MUST use an RFC 2119 keyword — a guarantee is a normative promise to a
    dependent, not descriptive prose."""
    findings = []
    for comp in corpus.components.values():
        for gid, doc in comp.interface_guarantees.items():
            header_m = GUARANTEE_ID_HEADER_RE.search(doc.body)
            if header_m and header_m.group(1) != gid:
                findings.append(Finding("R-LINT-017", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"file is named {gid}.md but its own heading says "
                                         f"{header_m.group(1)}"))
            if not any(kw in doc.body for kw in RFC2119_KEYWORDS):
                findings.append(Finding("R-LINT-017", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"{gid} uses no RFC 2119 keyword ({'/'.join(RFC2119_KEYWORDS)})"))
    return findings


def _collect_covers(doc: Doc) -> list[tuple[str, int]]:
    out = []
    for m in COVERS_RE.finditer(doc.body):
        out.append((m.group(1), _find_line(doc.body, m.group(0))))
    return out


def rule_forward_traceability(corpus: Corpus) -> list[Finding]:
    """R-LINT-008 — since D15, requirements and their covering criteria are
    each a directory listing, not a regex-parsed shared-file section."""
    findings = []
    for comp in corpus.components.values():
        if not comp.root:
            continue
        covered = {ref for doc in comp.acceptance.values() for ref, _ in _collect_covers(doc)}
        for rid, doc in comp.requirements.items():
            if rid not in covered:
                findings.append(Finding("R-LINT-008", SEVERITY_FAIL, doc.rel_path, 1,
                                         f"{rid} has zero covering acceptance criteria"))
    return findings


def rule_backward_traceability(corpus: Corpus) -> list[Finding]:
    """R-LINT-009 — Covers: must resolve to a real R-id (component-local) or
    P-id (corpus-wide product capability)."""
    findings = []
    all_r_ids: set[str] = {
        rid for comp in corpus.components.values() for rid in comp.requirements
    }
    all_p_ids = {d.doc_id for d in corpus.docs if d.doc_type == "product" and d.doc_id}

    for doc in corpus.docs:
        if doc.doc_type not in ("component-acceptance", "product"):
            continue
        for ref, line in _collect_covers(doc):
            if ref.startswith("R-") and ref not in all_r_ids:
                findings.append(Finding("R-LINT-009", SEVERITY_FAIL, doc.rel_path, line,
                                         f"Covers: {ref} does not resolve to any requirement"))
            elif ref.startswith("P-") and ref not in all_p_ids:
                findings.append(Finding("R-LINT-009", SEVERITY_FAIL, doc.rel_path, line,
                                         f"Covers: {ref} does not resolve to any product capability"))
            elif not ref.startswith("R-") and not ref.startswith("P-"):
                findings.append(Finding("R-LINT-009", SEVERITY_FAIL, doc.rel_path, line,
                                         f"Covers: {ref} is neither an R-id nor a P-id"))
    return findings


def _check_criterion_block(doc: Doc, name: str, block: str, line: int) -> list[Finding]:
    findings = []
    if not KIND_RE.search(block):
        findings.append(Finding("R-LINT-010", SEVERITY_FAIL, doc.rel_path, line,
                                 f"{name} is missing a Kind: tag"))
    if not COVERS_RE.search(block):
        findings.append(Finding("R-LINT-010", SEVERITY_FAIL, doc.rel_path, line,
                                 f"{name} is missing a Covers: tag"))
    gherkin = GHERKIN_BLOCK_RE.search(block)
    if not gherkin:
        findings.append(Finding("R-LINT-010", SEVERITY_FAIL, doc.rel_path, line,
                                 f"{name} has no gherkin block"))
    else:
        g = gherkin.group(1)
        for step in ("Given", "When", "Then"):
            if step not in g:
                findings.append(Finding("R-LINT-010", SEVERITY_FAIL, doc.rel_path, line,
                                         f"{name}'s gherkin block is missing a {step} step"))
    return findings


def rule_criterion_wellformed(corpus: Corpus) -> list[Finding]:
    """R-LINT-010. Branches on doc_type: a `component-acceptance` file (D15)
    *is* one criterion already, so the whole body is the block. A `product`
    capability doc is unaffected by D15 — it still holds multiple inline
    `### GS-...` golden scenarios in one file, so that case keeps the
    original header-splitting logic."""
    findings = []
    for doc in corpus.docs:
        if doc.doc_type == "component-acceptance":
            findings.extend(_check_criterion_block(doc, doc.doc_id, doc.body, 1))
        elif doc.doc_type == "product":
            headers = list(CRITERION_HEADER_RE.finditer(doc.body))
            for i, h in enumerate(headers):
                start = h.end()
                end = headers[i + 1].start() if i + 1 < len(headers) else len(doc.body)
                block = doc.body[start:end]
                name = h.group(1)
                line = _find_line(doc.body, h.group(0))
                findings.extend(_check_criterion_block(doc, name, block, line))
    return findings


def _token_overlap(a: str, b: str) -> float:
    """Normalized token-overlap ratio in [0, 1]: |intersection| / |union| of
    each text's lowercased word set. Deterministic, no model call — this is
    deliberately a blunt textual-similarity measure, not a semantic one; that
    split is exactly what separates R-LINT-011 (compiled) from R-LINT-015
    (llm-judge)."""
    wa, wb = set(WORD_RE.findall(a.lower())), set(WORD_RE.findall(b.lower()))
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


NEAR_VERBATIM_THRESHOLD = 0.8


def _definitions_glossary_entries(doc: Doc, glossary_defs: dict[str, str]) -> list[tuple[str, str, str]]:
    """Yield (term, local_text, matched_heading_text) for every entry in a
    component root's Definitions section whose term also exists in the
    glossary."""
    def_match = re.search(r"##\s*Definitions\s*\n(.*?)(\n##|\Z)", doc.body, re.DOTALL)
    if not def_match:
        return []
    section = def_match.group(1)
    out = []
    for m in GLOSSARY_ENTRY_RE.finditer(section):
        term = m.group(1).strip().lower()
        if term in glossary_defs:
            out.append((term, m.group(2).strip(), m.group(0)))
    return out


def rule_glossary_conformance(corpus: Corpus) -> list[Finding]:
    """R-LINT-011 — compiled, textual-similarity only.

    Resolved from an earlier heuristic that only checked "does the term name
    reappear," which couldn't tell a restatement from a legitimate delta.
    Now: a Definitions entry fails only when its text is a near-verbatim
    copy (token-overlap ratio >= NEAR_VERBATIM_THRESHOLD) of the glossary's
    own definition for that term — genuinely new, lower-overlap nuance is a
    permitted delta and does not fire this rule (see R-LINT-015 for the
    "same words, different meaning" case this can't catch by design).
    """
    findings = []
    for doc in corpus.docs:
        if doc.doc_type != "component-root":
            continue
        for term, local_text, heading in _definitions_glossary_entries(doc, corpus.glossary_defs):
            overlap = _token_overlap(local_text, corpus.glossary_defs[term])
            if overlap >= NEAR_VERBATIM_THRESHOLD:
                findings.append(Finding(
                    "R-LINT-011", SEVERITY_FAIL, doc.rel_path,
                    _find_line(doc.body, heading),
                    f"Definitions entry for '{term}' is a near-verbatim restatement "
                    f"of the glossary definition (token overlap {overlap:.2f}) — "
                    f"only deltas are permitted here"))
    return findings


def rule_llm_judge_glossary_conflict(corpus: Corpus, judge=None) -> list[Finding]:
    """R-LINT-015 — the one llm-judge rule in this component.

    `judge` is an injectable callable `(term: str, local_text: str,
    glossary_text: str) -> tuple[bool, str] | None` (returns
    `(conflicts, rationale)`, or None to mean "could not judge"). No real
    model is wired into this bootstrap — there is no model-call integration
    in a hand-authored CLI prototype, and faking one here would be dishonest
    about what was actually validated. When `judge` is not provided (the
    default — no model configured), every Definitions entry that reaches
    this rule is reported `skipped`, never silently passed, per D10's "tool
    must keep working" posture applied a third time.
    """
    findings = []
    for doc in corpus.docs:
        if doc.doc_type != "component-root":
            continue
        for term, local_text, heading in _definitions_glossary_entries(doc, corpus.glossary_defs):
            overlap = _token_overlap(local_text, corpus.glossary_defs[term])
            if overlap >= NEAR_VERBATIM_THRESHOLD:
                continue  # already R-LINT-011's job
            line = _find_line(doc.body, heading)
            if judge is None:
                findings.append(Finding(
                    "R-LINT-015", SEVERITY_SKIPPED, doc.rel_path, line,
                    f"no model configured — '{term}' not evaluated for "
                    f"semantic conflict with the glossary", rationale=None))
                continue
            result = judge(term, local_text, corpus.glossary_defs[term])
            if result is None:
                findings.append(Finding(
                    "R-LINT-015", SEVERITY_SKIPPED, doc.rel_path, line,
                    f"judge could not evaluate '{term}'", rationale=None))
                continue
            conflicts, rationale = result
            if conflicts:
                findings.append(Finding(
                    "R-LINT-015", SEVERITY_FAIL, doc.rel_path, line,
                    f"Definitions entry for '{term}' conflicts with the glossary "
                    f"definition", rationale=rationale))
    return findings


def _extract_first_fenced_block(body: str) -> str | None:
    """Return the content of the first fenced code block in `body`, or None.
    Since D15, a unit file like `interface/cli.md` *is* its own section — no
    `## CLI` heading to search under first, unlike the old shared-file
    parsing."""
    lines = body.splitlines()
    in_fence = False
    fence_lines: list[str] = []
    for line in lines:
        if line.strip().startswith("```"):
            if not in_fence:
                in_fence = True
                continue
            return "\n".join(fence_lines)
        if in_fence:
            fence_lines.append(line)
    return None


def _logical_lines(block: str) -> list[str]:
    """Join backslash line-continuations, then return non-blank logical
    lines — so a CLI invocation wrapped across physical lines still counts
    as one surface element, not two."""
    merged: list[str] = []
    buf = ""
    for raw in block.splitlines():
        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
        else:
            buf += stripped
            if buf.strip():
                merged.append(buf.strip())
            buf = ""
    if buf.strip():
        merged.append(buf.strip())
    return merged


LIBRARY_SIGNATURE_RE = re.compile(r"^\w+\(.*\)\s*(->|:)")


def _count_interface_surface(comp: Component) -> int:
    """R-LINT-012's 'interface surface elements' dimension.

    Since D15: one per distinct invocation line in `interface/cli.md`'s
    fenced block, plus one per distinct function-signature line in
    `interface/library.md`'s fenced block, plus one per file under
    `interface/data/` (each file already names exactly one type, by
    construction — no heading-counting needed, replacing the earlier "one
    per `## Data: ...` heading" approach now that headings aren't the unit
    boundary).

    Deliberately excludes `interface/guarantees/` (D16): a guarantee is
    cross-cutting behavioral narrative about the surface above, not itself
    a separate callable/addressable surface element — counting it here
    would conflate "how many things can you call" with "how many promises
    were made about them."
    """
    total = 0
    if comp.interface_cli:
        cli_block = _extract_first_fenced_block(comp.interface_cli.body)
        if cli_block:
            total += len(_logical_lines(cli_block))
    if comp.interface_library:
        lib_block = _extract_first_fenced_block(comp.interface_library.body)
        if lib_block:
            total += len([l for l in _logical_lines(lib_block) if LIBRARY_SIGNATURE_RE.match(l)])
    total += len(comp.interface_data)
    return total


def rule_size_caps(corpus: Corpus) -> list[Finding]:
    """R-LINT-012.

    Open question resolved: spec-bundle word count is computed from the
    source markdown of component.md + requirements/ + interface/
    (+ interface/data/) + acceptance/ + constraints.md as authored
    (pre-compilation) — a Gherkin block's compiled test scaffolding isn't
    spec-bundle text and doesn't exist until generation runs, so there is
    nothing to count post-compilation at lint time anyway.
    """
    findings = []
    CAPS = {
        "generated_code_loc": (800, 1500),
        "spec_bundle_words": (2000, 4000),
        "requirement_count": (20, 40),
        "interface_surface": (10, 20),
        "fan_out": (7, None),
        "fan_in": (10, None),
    }

    fan_in: dict[str, int] = {c: 0 for c in corpus.components}
    for comp in corpus.components.values():
        if not comp.root:
            continue
        for dep in comp.root.frontmatter.get("depends_on") or []:
            dep_doc = corpus.id_index.get(dep)
            if dep_doc and dep_doc.component in fan_in:
                fan_in[dep_doc.component] += 1

    for name, comp in corpus.components.items():
        if not comp.root:
            continue
        rel = comp.root.rel_path
        all_docs = (
            [comp.root] + list(comp.requirements.values())
            + ([comp.interface_cli] if comp.interface_cli else [])
            + ([comp.interface_library] if comp.interface_library else [])
            + list(comp.interface_data.values())
            + list(comp.interface_guarantees.values())
            + list(comp.acceptance.values())
            + ([comp.constraints] if comp.constraints else [])
        )
        word_count = sum(len(d.body.split()) for d in all_docs)
        req_count = len(comp.requirements)
        gen_dir = corpus.repo_root / "gen" / name
        loc = 0
        if gen_dir.is_dir():
            for f in gen_dir.rglob("*.py"):
                loc += sum(1 for l in f.read_text(encoding="utf-8").splitlines()
                           if l.strip() and not l.strip().startswith("#"))
        iface_surface = _count_interface_surface(comp)
        fan_out = len(comp.root.frontmatter.get("depends_on") or [])

        measurements = {
            "generated_code_loc": loc,
            "spec_bundle_words": word_count,
            "requirement_count": req_count,
            "interface_surface": iface_surface,
            "fan_out": fan_out,
            "fan_in": fan_in.get(name, 0),
        }
        for dim, value in measurements.items():
            warn_at, fail_at = CAPS[dim]
            if fail_at is not None and value > fail_at:
                findings.append(Finding("R-LINT-012", SEVERITY_FAIL, rel, 1,
                                         f"'{dim}' is {value}, exceeding hard-fail threshold {fail_at}"))
            elif value > warn_at:
                findings.append(Finding("R-LINT-012", SEVERITY_WARN, rel, 1,
                                         f"'{dim}' is {value}, exceeding warn threshold {warn_at}"))
    return findings


def rule_secret_field_safety(corpus: Corpus) -> list[Finding]:
    """R-LINT-013.

    Ambiguity resolved: SPEC_GUIDELINES.md §3.3 lists var fields
    (required/type/sensitivity/description/example/default) without saying
    whether they're frontmatter or body content. The actual example files
    use body bullets (`- **sensitivity:** secret`), not frontmatter, so this
    rule parses body bullets. Unaffected by D15 — `specs/vars/` declarations
    were already one flat file per variable before D15 and stay that way.
    """
    findings = []
    for doc in corpus.docs:
        if doc.doc_type != "var":
            continue
        sensitivity_match = re.search(r"\*\*sensitivity:\*\*\s*(\S+)", doc.body)
        if not sensitivity_match or sensitivity_match.group(1) != "secret":
            continue
        for forbidden in ("example", "default"):
            m = re.search(rf"\*\*{forbidden}:\*\*", doc.body)
            if m:
                findings.append(Finding("R-LINT-013", SEVERITY_FAIL, doc.rel_path,
                                         _find_line(doc.body, m.group(0)),
                                         f"sensitivity: secret but carries a '{forbidden}' field"))
    return findings


def rule_glossary_singularity(corpus: Corpus) -> list[Finding]:
    """R-LINT-014. Unaffected by D15."""
    findings = []
    canonical = corpus.repo_root / "specs" / "glossary.md"
    extra = [p for p in corpus.glossary_files if p != canonical]
    if not extra:
        return findings
    split_recorded = False
    for doc in corpus.docs:
        if doc.doc_type == "architecture" and "bounded-context" in doc.body.lower() and "glossary" in doc.body.lower():
            split_recorded = True
            break
    if not split_recorded:
        for p in extra:
            findings.append(Finding("R-LINT-014", SEVERITY_FAIL, str(p.relative_to(corpus.repo_root)), 1,
                                     "additional glossary-like file with no recorded architecture-level "
                                     "bounded-context split decision (D14)"))
    return findings


def rule_no_trailing_whitespace(corpus: Corpus) -> list[Finding]:
    """R-LINT-019. Resolves item 9's cache-hit-rate concern by keeping
    cosmetic byte differences out of committed files, rather than teaching
    spec_bundle_hash a normalization rule that Markdown's own
    whitespace-sensitive constructs (CommonMark hard line breaks, nested-list
    indentation) could make unsafe. Scans every file that can reach
    spec_bundle_hash's input: corpus.docs plus the glossary (which
    rule-loading excludes from corpus.docs to avoid double-definition
    parsing, per `_load_corpus`).
    """
    findings = []
    paths = [doc.path for doc in corpus.docs] + list(corpus.glossary_files)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(corpus.repo_root))
        for i, line in enumerate(text.splitlines(), start=1):
            if line != line.rstrip():
                findings.append(Finding("R-LINT-019", SEVERITY_FAIL, rel, i,
                                         "line has trailing whitespace"))
    return findings


ALL_RULES = [
    rule_frontmatter_completeness,
    rule_no_stray_frontmatter,
    rule_ratified_closure,
    rule_reference_resolution,
    rule_depends_on_guarantees_resolution,
    rule_acyclic_graph,
    rule_sealed_consistency,
    rule_realizes_coverage,
    rule_requirement_identity,
    rule_guarantee_identity,
    rule_forward_traceability,
    rule_backward_traceability,
    rule_criterion_wellformed,
    rule_glossary_conformance,
    rule_size_caps,
    rule_secret_field_safety,
    rule_glossary_singularity,
    rule_no_trailing_whitespace,
]


# ---------------------------------------------------------------------------
# Public library entry point
# ---------------------------------------------------------------------------

def lint(paths: list[Path] | None, repo_root: Path, strict: bool = False, judge=None) -> LintReport:
    """Pure function over the filesystem state at repo_root, for 15 of 16
    rules — no network access, no model calls, no side effects (per
    constraints.md). The exception is R-LINT-015, which takes an optional
    `judge` callable; omit it (the default) to run in single-model-absent
    mode, where R-LINT-015 reports `skipped` rather than running, silently
    passing, or crashing."""
    corpus = load_corpus(repo_root)

    if paths:
        wanted = {str(p.resolve()) for p in paths}
        corpus.docs = [
            d for d in corpus.docs
            if str(d.path.resolve()) in wanted
            or any(str(d.path.resolve()).startswith(str(Path(w).resolve()) + "/") for w in wanted)
            or str(d.path.resolve()) in {str(Path(w).resolve()) for w in wanted}
        ]

    report = LintReport()
    for rule in ALL_RULES:
        report.findings.extend(rule(corpus))
    report.findings.extend(rule_llm_judge_glossary_conflict(corpus, judge=judge))

    if strict:
        # skipped findings are deliberately never escalated — "not evaluated"
        # is not the same thing as "warned," and --strict only tightens
        # warn-vs-fail, not evaluated-vs-skipped.
        report.findings = [
            Finding(f.rule_id, SEVERITY_FAIL, f.file, f.line, f.message) if f.severity == SEVERITY_WARN else f
            for f in report.findings
        ]
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs lint")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code != 0 else 0

    repo_root = args.repo_root
    if repo_root is None:
        cur = Path.cwd()
        while cur != cur.parent and not (cur / ".git").exists():
            cur = cur.parent
        repo_root = cur
    if not (repo_root / "specs").is_dir():
        print(f"error: no specs/ directory found under {repo_root}", file=sys.stderr)
        return 2

    report = lint(args.paths or None, repo_root, strict=args.strict)
    if args.format == "json":
        print(json.dumps(report.to_json(), indent=2))
    else:
        print(report.to_text())
    return 1 if report.hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())
