"""citation-checker: checks that every citation in a spec corpus resolves.

Rules R-CITE-001 .. R-CITE-005. Read-only and deterministic.
"""

import importlib.util
import re
import sys
from pathlib import Path

_EXEMPT = range(1, 15)  # D1-D14, frozen at the baseline reset, never files
_D_RE = re.compile(r"\bD(\d+)\b")
_PTR_RE = re.compile(r"`([^`]*)`'s\s+\"([^\"]*)\"\s+section")
_GLOSS_RE = re.compile(r"the\s+glossary's\s+\"([^\"]*)\"")
_HEADING_RE = re.compile(r"^#+\s+(.*?)\s*$")
_ENTRY_RE = re.compile(r"^- \*\*(.+?)\*\*")
_DNUM_RE = re.compile(r"D(\d+)")


def _get(obj, name):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_dep(repo_root, slug, module_name):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        init = base / module_name / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            module_name, init, submodule_search_locations=[str(init.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _finding(rule_id, rel_path, line, message):
    return {
        "rule_id": rule_id,
        "severity": "fail",
        "file": rel_path,
        "line": line,
        "message": message,
    }


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _body_offset(doc, body):
    lines = _read(_get(doc, "path")).splitlines()
    return max(len(lines) - len(body.split("\n")), 0)


def _line_at(body, pos, offset):
    return body.count("\n", 0, pos) + 1 + offset


def _key_line(doc, key):
    for i, line in enumerate(_read(_get(doc, "path")).splitlines(), 1):
        if line.split(":", 1)[0].strip() == key:
            return i
    return 1


def _values(frontmatter, key):
    value = frontmatter.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    return [str(v) for v in value if v]


def _exempt(value):
    m = _DNUM_RE.fullmatch(value)
    return bool(m) and int(m.group(1)) in _EXEMPT


def _glossary_terms(repo_root):
    path = Path(repo_root) / "specs" / "glossary.md"
    if not path.is_file():
        return set()
    terms = set()
    for line in _read(path).splitlines():
        m = _ENTRY_RE.match(line)
        if m:
            terms.add(" ".join(m.group(1).split()))
    return terms


def _headings(path):
    found = set()
    for line in _read(path).splitlines():
        m = _HEADING_RE.match(line)
        if m:
            found.add(m.group(1))
    return found


def _check_live(doc, repo_root, decisions, glossary):
    rel = _get(doc, "rel_path")
    body = _get(doc, "body")
    offset = _body_offset(doc, body)
    out = []

    for m in _D_RE.finditer(body):
        n = int(m.group(1))
        if n in _EXEMPT or f"D{n}" in decisions:
            continue
        out.append(_finding(
            "R-CITE-001", rel, _line_at(body, m.start(), offset),
            f"D{n} does not resolve to specs/decisions/D{n}.md",
        ))

    for m in _PTR_RE.finditer(body):
        target = re.sub(r"\s+", "", m.group(1))
        if target.startswith("<"):
            continue
        section = m.group(2)
        line = _line_at(body, m.start(), offset)
        path = Path(repo_root) / target
        if not path.is_file():
            out.append(_finding(
                "R-CITE-002", rel, line,
                f"pointer to {target}'s \"{section}\" section: file {target} does not exist",
            ))
        elif section not in _headings(path):
            out.append(_finding(
                "R-CITE-002", rel, line,
                f"pointer to {target}'s \"{section}\" section: no heading \"{section}\" in {target}",
            ))

    for m in _GLOSS_RE.finditer(body):
        term = " ".join(m.group(1).split())
        if term.endswith((",", ".", ";", ":")):
            term = term[:-1]
        if not term[:1].isalnum():
            continue
        if term in glossary:
            continue
        out.append(_finding(
            "R-CITE-003", rel, _line_at(body, m.start(), offset),
            f"glossary citation \"{term}\" does not resolve to an entry in specs/glossary.md",
        ))

    return out


def _check_decision(doc, decisions, supersedes_pairs):
    rel = _get(doc, "rel_path")
    stem = Path(rel).stem
    frontmatter = _get(doc, "frontmatter")
    out = []

    for value in _values(frontmatter, "supersedes"):
        if _exempt(value):
            continue
        target = decisions.get(value)
        if target is None:
            out.append(_finding(
                "R-CITE-004", rel, _key_line(doc, "supersedes"),
                f"supersedes: {value} does not resolve to specs/decisions/{value}.md",
            ))
        elif _get(target, "frontmatter").get("status") != "deprecated":
            out.append(_finding(
                "R-CITE-004", rel, _key_line(doc, "supersedes"),
                f"supersedes: {value}, but specs/decisions/{value}.md is not status: deprecated",
            ))

    if frontmatter.get("status") == "deprecated":
        named = any(v == stem and sup != stem for sup, v in supersedes_pairs)
        if not named:
            out.append(_finding(
                "R-CITE-004", rel, _key_line(doc, "status"),
                f"{stem} is status: deprecated but no other decision supersedes it",
            ))

    for value in _values(frontmatter, "builds_on"):
        if _exempt(value) or value in decisions:
            continue
        out.append(_finding(
            "R-CITE-005", rel, _key_line(doc, "builds_on"),
            f"builds_on: {value} does not resolve to specs/decisions/{value}.md",
        ))

    return out


def check(repo_root: Path) -> list:
    corpus_loader = _load_dep(repo_root, "corpus-loader", "corpus_loader")
    corpus = corpus_loader.load_corpus(repo_root)
    docs = list(_get(corpus, "docs"))

    decisions = {}
    for doc in docs:
        if _get(doc, "doc_type") == "decision":
            decisions[Path(_get(doc, "rel_path")).stem] = doc

    supersedes_pairs = [
        (stem, value)
        for stem, doc in decisions.items()
        for value in _values(_get(doc, "frontmatter"), "supersedes")
    ]
    glossary = _glossary_terms(repo_root)

    findings = []
    for doc in docs:
        if _get(doc, "doc_type") == "decision":
            findings.extend(_check_decision(doc, decisions, supersedes_pairs))
        else:
            findings.extend(_check_live(doc, repo_root, decisions, glossary))
    return findings
