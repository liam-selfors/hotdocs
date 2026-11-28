"""Citation checker: resolves decision, section-pointer, glossary,
`supersedes` and `builds_on` citations in a spec corpus."""

import importlib.util
import re
import sys
from pathlib import Path

_DEP_SLUG = "corpus-loader"
_DEP_MODULE = "corpus_loader"

_D_CITE = re.compile(r"\bD(\d+)\b")
_SECTION_PTR = re.compile(r"`([^`]*)`'s\s+\"([^\"]*)\"\s+section")
_GLOSSARY_CITE = re.compile(r"the\s+glossary's\s+\"([^\"]*)\"")
_HEADING = re.compile(r"^#+\s+(.*?)\s*$")
_GLOSSARY_ENTRY = re.compile(r"^- \*\*(.+?)\*\*")
_D_ID = re.compile(r"D(\d+)")


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _dep_dir(repo_root, slug):
    d = Path(repo_root) / "gen" / slug
    if d.is_dir():
        return d
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent / "gen" / slug
    return d


def _load_corpus_loader(repo_root):
    d = _dep_dir(repo_root, _DEP_SLUG)
    pkg_init = d / _DEP_MODULE / "__init__.py"
    if pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            _DEP_MODULE, pkg_init, submodule_search_locations=[str(pkg_init.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location(_DEP_MODULE, d / f"{_DEP_MODULE}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_DEP_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


def _finding(rule_id, file, line, message):
    return {
        "rule_id": rule_id,
        "severity": "fail",
        "file": file,
        "line": line,
        "message": message,
    }


def _exempt(entry):
    m = _D_ID.fullmatch(entry)
    return bool(m) and 1 <= int(m.group(1)) <= 14


def _items(value):
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)] if value else []


def _body_offset(path, body):
    text = Path(path).read_text(encoding="utf-8")
    if body == text:
        return 0
    return len(text.splitlines()) - body.count("\n") - 1


def _key_line(path, key):
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
        if line.startswith(f"{key}:"):
            return i + 1
    return 1


def _headings(path):
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _HEADING.match(line)
        if m:
            out.add(m.group(1))
    return out


def _glossary_terms(repo_root):
    gpath = Path(repo_root) / "specs" / "glossary.md"
    terms = set()
    if gpath.is_file():
        for line in gpath.read_text(encoding="utf-8").splitlines():
            m = _GLOSSARY_ENTRY.match(line)
            if m:
                terms.add(" ".join(m.group(1).split()))
    return terms


def _check_live(doc, repo_root, decisions, glossary_cache):
    rel = _get(doc, "rel_path")
    body = _get(doc, "body") or ""
    offset = _body_offset(_get(doc, "path"), body)
    out = []

    def line_of(pos):
        return offset + body.count("\n", 0, pos) + 1

    for m in _D_CITE.finditer(body):
        n = int(m.group(1))
        if 1 <= n <= 14 or f"specs/decisions/D{n}.md" in decisions:
            continue
        out.append(_finding(
            "R-CITE-001", rel, line_of(m.start()),
            f"D{n} does not resolve to specs/decisions/D{n}.md",
        ))

    for m in _SECTION_PTR.finditer(body):
        target = re.sub(r"\s+", "", m.group(1))
        if target.startswith("<"):
            continue
        section = m.group(2)
        tpath = Path(repo_root) / target
        if not tpath.is_file():
            out.append(_finding(
                "R-CITE-002", rel, line_of(m.start()),
                f"pointer to `{target}`'s \"{section}\" section: file does not exist",
            ))
        elif section not in _headings(tpath):
            out.append(_finding(
                "R-CITE-002", rel, line_of(m.start()),
                f"pointer to `{target}`'s \"{section}\" section: no heading matches",
            ))

    for m in _GLOSSARY_CITE.finditer(body):
        raw = m.group(1)
        if not raw[:1].isalnum():
            continue
        term = raw[:-1] if raw[-1] in ",.;:" else raw
        term = " ".join(term.split())
        if "terms" not in glossary_cache:
            glossary_cache["terms"] = _glossary_terms(repo_root)
        if term not in glossary_cache["terms"]:
            out.append(_finding(
                "R-CITE-003", rel, line_of(m.start()),
                f"glossary citation \"{term}\" does not resolve to an entry in specs/glossary.md",
            ))
    return out


def _check_decision(doc, decisions, named):
    rel = _get(doc, "rel_path")
    path = _get(doc, "path")
    fm = _get(doc, "frontmatter") or {}
    out = []

    for entry in _items(_get(fm, "supersedes")):
        if _exempt(entry):
            continue
        target = decisions.get(f"specs/decisions/{entry}.md")
        if target is None:
            out.append(_finding(
                "R-CITE-004", rel, _key_line(path, "supersedes"),
                f"supersedes: {entry} does not resolve to specs/decisions/{entry}.md",
            ))
        elif _get(_get(target, "frontmatter") or {}, "status") != "deprecated":
            out.append(_finding(
                "R-CITE-004", rel, _key_line(path, "supersedes"),
                f"supersedes: {entry}, but {entry}'s status is not deprecated",
            ))

    if _get(fm, "status") == "deprecated" and rel not in named:
        out.append(_finding(
            "R-CITE-004", rel, _key_line(path, "status"),
            "status: deprecated, but no other decision's supersedes names this record",
        ))

    for entry in _items(_get(fm, "builds_on")):
        if _exempt(entry) or f"specs/decisions/{entry}.md" in decisions:
            continue
        out.append(_finding(
            "R-CITE-005", rel, _key_line(path, "builds_on"),
            f"builds_on: {entry} does not resolve to specs/decisions/{entry}.md",
        ))
    return out


def check(repo_root: Path) -> list:
    loader = _load_corpus_loader(repo_root)
    corpus = loader.load_corpus(repo_root)
    docs = list(_get(corpus, "docs") or [])

    decisions = {
        _get(d, "rel_path"): d for d in docs if _get(d, "doc_type") == "decision"
    }
    named = set()
    for rel, d in decisions.items():
        for entry in _items(_get(_get(d, "frontmatter") or {}, "supersedes")):
            target = f"specs/decisions/{entry}.md"
            if target != rel:
                named.add(target)

    glossary_cache = {}
    findings = []
    for doc in docs:
        if _get(doc, "doc_type") == "decision":
            findings.extend(_check_decision(doc, decisions, named))
        else:
            findings.extend(_check_live(doc, repo_root, decisions, glossary_cache))
    findings.sort(key=lambda f: f["file"])
    return findings
