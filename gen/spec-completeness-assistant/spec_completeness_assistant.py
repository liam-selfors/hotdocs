"""Spec Completeness Assistant: advisory completeness checks for a spec change.

Advisory only (R-ASSIST-006): nothing here blocks, gates or fails a merge.
"""

import dataclasses
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

_RID_RE = re.compile(r"R-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]+[a-z]?")
_WORD_RE = re.compile(r"[a-z0-9_]{3,}")
_JACCARD_THRESHOLD = 0.35
_MAX_CANDIDATES = 5

_USAGE = (
    "usage: hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] "
    "[--format=json|text] [--model=<model>]"
)


@dataclasses.dataclass
class CompletenessReport:
    lint_findings: list
    halted: bool
    predicted_blast_radius: list
    criterion_reviews: dict
    completeness_score: object
    completeness_rationale: object
    redundancy_flags: list
    degraded: bool

    def to_dict(self):
        return {
            "lint_findings": [_finding_dict(f) for f in self.lint_findings],
            "halted": self.halted,
            "predicted_blast_radius": list(self.predicted_blast_radius),
            "criterion_reviews": dict(self.criterion_reviews),
            "completeness_score": self.completeness_score,
            "completeness_rationale": self.completeness_rationale,
            "redundancy_flags": [dict(e) for e in self.redundancy_flags],
            "degraded": self.degraded,
        }


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _finding_dict(f):
    if isinstance(f, dict):
        return f
    d = {k: getattr(f, k) for k in ("rule_id", "severity", "file", "line", "message")}
    rationale = getattr(f, "rationale", None)
    if rationale is not None:
        d["rationale"] = rationale
    return d


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load(root, slug, module):
    directory = root / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    spec = importlib.util.spec_from_file_location(module, directory / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    return path.read_text(encoding="utf-8")


class _Scan:
    def __init__(self):
        self.slugs = []
        self.changed_reqs = []
        self.req_index = {}
        self.acceptance = {}


def _scan(root, changed_ids):
    scan = _Scan()
    comps_dir = root / "specs" / "components"
    if not comps_dir.is_dir():
        return scan
    crit_index = {}
    comp_slugs = []
    for d in sorted(p for p in comps_dir.iterdir() if p.is_dir()):
        comp_slugs.append(d.name)
        for req in sorted((d / "requirements").glob("R-*.md")):
            scan.req_index[req.stem] = (d.name, req)
        crits = sorted((d / "acceptance").glob("AC-*.md"))
        scan.acceptance[d.name] = crits
        for crit in crits:
            crit_index[crit.stem] = d.name

    def add_slug(slug):
        if slug not in scan.slugs:
            scan.slugs.append(slug)

    def add_req(rid):
        if rid not in scan.changed_reqs:
            scan.changed_reqs.append(rid)

    for cid in changed_ids:
        if cid.startswith("comp-"):
            slug = cid[len("comp-"):]
            if slug in comp_slugs:
                add_slug(slug)
                for rid, (rslug, _path) in sorted(scan.req_index.items()):
                    if rslug == slug:
                        add_req(rid)
        elif cid in scan.req_index:
            add_slug(scan.req_index[cid][0])
            add_req(cid)
        elif cid in crit_index:
            add_slug(crit_index[cid])
    return scan


def _inside(finding, root, slugs):
    f = str(_get(finding, "file"))
    if os.path.isabs(f):
        f = os.path.relpath(f, root)
    f = f.replace(os.sep, "/")
    return any(f.startswith(f"specs/components/{slug}/") for slug in slugs)


def _covers(text, rid):
    for line in text.splitlines():
        if "Covers:" in line:
            rest = line.split("Covers:", 1)[1]
            if rid in _RID_RE.findall(rest):
                return True
    return False


def _completeness_prompt(scan, criterion_reviews, inside_findings):
    parts = [
        "You are reviewing a proposed spec change for completeness, before it is "
        "submitted. Below are the changed requirements, each followed by its "
        "covering acceptance criteria, then deterministic findings.",
        "",
        "## Changed requirements",
    ]
    for rid in scan.changed_reqs:
        slug, path = scan.req_index[rid]
        parts.append(f"### Requirement {rid}")
        parts.append(_read(path))
        covering = []
        for crit in scan.acceptance[slug]:
            text = _read(crit)
            if _covers(text, rid):
                covering.append((crit.stem, text))
        if not covering:
            parts.append(f"No acceptance criterion covers {rid}.")
        for aid, text in covering:
            parts.append(f"#### Covering criterion {aid}")
            parts.append(text)
    parts.append("")
    parts.append("## invisible_reference findings for the changed components")
    for slug in scan.slugs:
        review = criterion_reviews.get(f"comp-{slug}")
        for f in _get(review, "findings") or []:
            if _get(f, "kind") == "invisible_reference":
                parts.append(json.dumps(f, default=str))
    parts.append("")
    parts.append("## Lint findings inside the changed components")
    for f in inside_findings:
        parts.append(json.dumps(_finding_dict(f), default=str))
    parts.append("")
    parts.append(
        "Questions:\n"
        "1. Do each changed requirement's criteria check what it states?\n"
        "2. Does a dependent component's interface/ need a matching update "
        "that was not made?\n"
        "3. Does any criterion expect behavior no requirement states?\n"
        "\n"
        "Reply with only a JSON object of the form "
        '{"completeness_score": <number from 0.0 to 1.0>, '
        '"completeness_rationale": "<text>"}.'
    )
    return "\n".join(parts)


def _words(text):
    return set(_WORD_RE.findall(_RID_RE.sub("", text).lower()))


def _jaccard(a, b):
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _candidates(scan):
    changed = set(scan.changed_reqs)
    others = [
        (rid, _read(path))
        for rid, (_slug, path) in sorted(scan.req_index.items())
        if rid not in changed
    ]
    other_words = [(rid, text, _words(text)) for rid, text in others]
    pairs = []
    for rid in scan.changed_reqs:
        text = _read(scan.req_index[rid][1])
        words = _words(text)
        scored = []
        for oid, otext, owords in other_words:
            score = _jaccard(words, owords)
            if score >= _JACCARD_THRESHOLD:
                scored.append((-score, oid, otext))
        scored.sort(key=lambda t: (t[0], t[1]))
        for _neg, oid, otext in scored[:_MAX_CANDIDATES]:
            pairs.append((rid, text, oid, otext))
    return pairs


def _redundancy_prompt(pairs):
    parts = [
        "Each pair below holds a changed requirement and an existing requirement "
        "elsewhere in the spec corpus. Decide which pairs describe the same "
        "behavior.",
        "",
    ]
    for i, (rid, text, oid, otext) in enumerate(pairs, 1):
        parts.append(f"## Pair {i}: {rid} / {oid}")
        parts.append(f"### {rid}")
        parts.append(text)
        parts.append(f"### {oid}")
        parts.append(otext)
        parts.append("")
    parts.append(
        "Reply with only a JSON object of the form "
        '{"redundancy_flags": [{"new_requirement": "<changed R-id>", '
        '"overlaps_with": "<other R-id>", "rationale": "<text>"}, ...]}, '
        "listing only the pairs that describe the same behavior."
    )
    return "\n".join(parts)


def _reply_obj(resp):
    if _get(resp, "model_call_error") is not None:
        return None
    text = _get(resp, "text")
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    lines = stripped.splitlines()
    if (
        len(lines) >= 2
        and lines[0].rstrip() in ("```", "```json")
        and lines[-1].rstrip() == "```"
    ):
        stripped = "\n".join(lines[1:-1])
    try:
        return json.loads(stripped)
    except ValueError:
        return None


def _parse_completeness(resp):
    obj = _reply_obj(resp)
    if not isinstance(obj, dict):
        return None, None
    score = obj.get("completeness_score")
    rationale = obj.get("completeness_rationale")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None, None
    if not isinstance(rationale, str) or not rationale:
        return None, None
    return min(1.0, max(0.0, score)) if not 0.0 <= score <= 1.0 else score, rationale


def _parse_redundancy(resp, candidate_set):
    obj = _reply_obj(resp)
    if not isinstance(obj, dict) or not isinstance(obj.get("redundancy_flags"), list):
        return []
    keys = ("new_requirement", "overlaps_with", "rationale")
    flags = []
    for entry in obj["redundancy_flags"]:
        if not isinstance(entry, dict):
            continue
        if not all(isinstance(entry.get(k), str) and entry.get(k) for k in keys):
            continue
        if (entry["new_requirement"], entry["overlaps_with"]) not in candidate_set:
            continue
        flags.append({k: entry[k] for k in keys})
    return flags


def assist(changed_ids, repo_root, model=None, *, llm_backend=None):
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        return _assist(changed_ids, repo_root, model, llm_backend)
    finally:
        sys.dont_write_bytecode = previous


def _assist(changed_ids, repo_root, model, llm_backend):
    root = Path(repo_root)
    mods = {}

    def dep(slug, module):
        if slug not in mods:
            mods[slug] = _load(root, slug, module)
        return mods[slug]

    degraded = model is None
    judge = None
    if model is not None:
        judge = dep("spec-reviewer", "spec_reviewer").glossary_judge(model, llm_backend)
    lint_report = dep("spec-linter", "spec_linter").lint(None, repo_root, judge=judge)
    findings = list(_get(lint_report, "findings"))

    scan = _scan(root, changed_ids)
    inside_findings = [f for f in findings if _inside(f, root, scan.slugs)]
    if any(_get(f, "severity") == "fail" for f in inside_findings):
        return CompletenessReport(findings, True, [], {}, None, None, [], degraded)

    blast = dep("impact-analyzer", "impact_analyzer").compute_blast_radius(
        changed_ids, repo_root
    )
    if _get(blast, "precondition_error") is not None:
        radius = []
    else:
        radius = [_get(e, "component_id") for e in _get(blast, "impacted")]

    reviews = {}
    for cid in radius:
        try:
            result = dep("spec-reviewer", "spec_reviewer").check([cid], repo_root)
            reviews[cid] = result if isinstance(result, dict) else result.to_dict()
        except Exception as exc:  # noqa: BLE001 -- R-ASSIST-003
            reviews[cid] = {"error": str(exc)}

    if model is None:
        return CompletenessReport(findings, False, radius, reviews, None, None, [], True)

    llm = dep("llm-endpoint", "llm_endpoint")
    prompt = _completeness_prompt(scan, reviews, inside_findings)
    score, rationale = _parse_completeness(llm.complete(prompt, model, backend=llm_backend))

    flags = []
    pairs = _candidates(scan)
    if pairs:
        candidate_set = {(rid, oid) for rid, _t, oid, _o in pairs}
        resp = llm.complete(_redundancy_prompt(pairs), model, backend=llm_backend)
        flags = _parse_redundancy(resp, candidate_set)

    return CompletenessReport(
        findings, False, radius, reviews, score, rationale, flags, False
    )


class _UsageError(Exception):
    pass


def _parse_args(argv):
    changed = []
    opts = {"repo-root": ".", "format": "text", "model": None}
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("--") and "=" in token:
            name, value = token[2:].split("=", 1)
        else:
            name, value = token[2:] if token.startswith("--") else None, None
        if name not in ("changed", "repo-root", "format", "model"):
            raise _UsageError(f"unknown argument: {token}")
        if value is None:
            if i + 1 >= len(argv):
                raise _UsageError(f"--{name} requires a value")
            i += 1
            value = argv[i]
        if name == "changed":
            changed.extend(part for part in value.split(",") if part)
        else:
            opts[name] = value
        i += 1
    if not changed:
        raise _UsageError("--changed is required")
    if opts["format"] not in ("json", "text"):
        raise _UsageError(f"invalid --format: {opts['format']}")
    return changed, opts


def _render_text(report):
    lines = []
    for f in report.lint_findings:
        lines.append(
            f"lint: {_get(f, 'rule_id')} {_get(f, 'severity')} "
            f"{_get(f, 'file')}:{_get(f, 'line')}: {_get(f, 'message')}"
        )
    if report.halted:
        lines.append("halted: a fail finding lies inside a changed component")
    for cid in report.predicted_blast_radius:
        review = report.criterion_reviews.get(cid, {})
        count = len(_get(review, "findings") or [])
        lines.append(f"blast radius: {cid}: {count} criterion review findings")
    if report.completeness_score is not None:
        lines.append(f"completeness_score: {str(report.completeness_score)}")
    if report.completeness_rationale is not None:
        lines.append(f"completeness_rationale: {report.completeness_rationale}")
    for e in report.redundancy_flags:
        lines.append(
            f"redundancy: {e['new_requirement']} overlaps {e['overlaps_with']}: "
            f"{e['rationale']}"
        )
    lines.append(f"degraded: {str(report.degraded).lower()}")
    return "\n".join(lines)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        changed, opts = _parse_args(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    report = assist(changed, Path(opts["repo-root"]), opts["model"])
    if opts["format"] == "json":
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(_render_text(report))
    return 1 if report.halted else 0


if __name__ == "__main__":
    sys.exit(main())
