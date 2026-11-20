"""Spec Completeness Assistant: advisory completeness/redundancy checks.

Advisory only: nothing here gates, blocks, or exits a build (R-ASSIST-006).
"""

import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_ID_RE = re.compile(r"R-[A-Z0-9]+(-[A-Z0-9]+)*-[0-9]+[a-z]?")
_WORD_RE = re.compile(r"[a-z0-9_]{3,}")
_FENCE_OPEN_RE = re.compile(r"```(json)?")
_THRESHOLD = 0.35
_TOP_N = 5
_FINDING_FIELDS = ("rule_id", "severity", "file", "line", "message")
_FLAG_FIELDS = ("new_requirement", "overlaps_with", "rationale")

USAGE = ("usage: hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] "
         "[--format=json|text] [--model=<model>]")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _finding_dict(f):
    if isinstance(f, dict):
        return f
    d = {k: getattr(f, k) for k in _FINDING_FIELDS}
    rationale = getattr(f, "rationale", None)
    if rationale is not None:
        d["rationale"] = rationale
    return d


@dataclass
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


def _tool_root():
    for p in Path(__file__).resolve().parents:
        if p.name == "gen":
            return p.parent
    return None


def _load(repo_root, slug, module):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    spec = importlib.util.spec_from_file_location(module, base / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _scan(root):
    comps = root / "specs" / "components"
    reqs = {}
    for p in sorted(comps.glob("*/requirements/*.md")):
        reqs[p.stem] = (p.parent.parent.name, p)
    acs = {}
    for p in sorted(comps.glob("*/acceptance/*.md")):
        acs[p.stem] = (p.parent.parent.name, p)
    return reqs, acs


def _read(path):
    return path.read_text(encoding="utf-8")


def _covers(text, rid):
    for line in text.splitlines():
        if "Covers:" in line:
            after = line.split("Covers:", 1)[1]
            if rid in [m.group(0) for m in _ID_RE.finditer(after)]:
                return True
    return False


def _words(text):
    return set(_WORD_RE.findall(_ID_RE.sub("", text).lower()))


def _jaccard(a, b):
    if a == b:
        return 1.0
    return len(a & b) / len(a | b)


def _parse(text):
    s = text.strip()
    lines = s.splitlines()
    if (len(lines) >= 2 and _FENCE_OPEN_RE.fullmatch(lines[0].strip())
            and lines[-1].strip() == "```"):
        s = "\n".join(lines[1:-1])
    try:
        return json.loads(s)
    except ValueError:
        return None


def _reply_data(response):
    if _get(response, "model_call_error") is not None:
        return None
    return _parse(_get(response, "text"))


def assist(changed_ids, repo_root, model=None, *, llm_backend=None):
    root = Path(repo_root)
    degraded = model is None
    reqs, acs = _scan(root)

    changed_slugs = []
    changed_reqs = []
    for cid in changed_ids:
        if cid.startswith("comp-"):
            slug = cid[len("comp-"):]
            if slug not in changed_slugs:
                changed_slugs.append(slug)
            for rid, (rslug, _p) in reqs.items():
                if rslug == slug and rid not in changed_reqs:
                    changed_reqs.append(rid)
        else:
            for index in (reqs, acs):
                if cid in index and index[cid][0] not in changed_slugs:
                    changed_slugs.append(index[cid][0])
            if cid in reqs and cid not in changed_reqs:
                changed_reqs.append(cid)

    def inside(f):
        file = str(_get(f, "file", "")).replace("\\", "/")
        return any(file.startswith(f"specs/components/{s}/") for s in changed_slugs)

    judge = None
    if not degraded:
        reviewer = _load(repo_root, "spec-reviewer", "spec_reviewer")
        judge = reviewer.glossary_judge(model, llm_backend)
    linter = _load(repo_root, "spec-linter", "spec_linter")
    lint_report = linter.lint(None, repo_root, judge=judge)
    findings = list(_get(lint_report, "findings", []))

    if any(_get(f, "severity") == "fail" and inside(f) for f in findings):
        return CompletenessReport(findings, True, [], {}, None, None, [], degraded)

    analyzer = _load(repo_root, "impact-analyzer", "impact_analyzer")
    br = analyzer.compute_blast_radius(changed_ids, repo_root)
    blast = []
    if _get(br, "precondition_error") is None:
        blast = [_get(e, "component_id") for e in _get(br, "impacted", [])]

    reviewer = _load(repo_root, "spec-reviewer", "spec_reviewer")
    reviews = {}
    for comp_id in blast:
        try:
            r = reviewer.check([comp_id], repo_root)
            reviews[comp_id] = r if isinstance(r, dict) else r.to_dict()
        except Exception as exc:
            reviews[comp_id] = {"error": str(exc)}

    report = CompletenessReport(findings, False, blast, reviews, None, None, [], degraded)
    if degraded:
        return report

    endpoint = _load(repo_root, "llm-endpoint", "llm_endpoint")

    # Completeness (R-ASSIST-004).
    parts = ["# Changed requirements and their covering criteria", ""]
    for rid in changed_reqs:
        slug, rpath = reqs[rid]
        parts.append(f"## Requirement {rid}")
        parts.append(_read(rpath))
        covering = [p for (aslug, p) in acs.values()
                    if aslug == slug and _covers(_read(p), rid)]
        if covering:
            for p in covering:
                parts.append(f"### Covering criterion {p.stem}")
                parts.append(_read(p))
        else:
            parts.append(f"No acceptance criterion covers {rid}.")
        parts.append("")
    parts.append("# invisible_reference findings for the changed components")
    for slug in changed_slugs:
        review = reviews.get(f"comp-{slug}", {})
        for f in review.get("findings", []) or []:
            if _get(f, "kind") == "invisible_reference":
                parts.append(json.dumps(_finding_dict(f) if not isinstance(f, dict) else f,
                                        default=str))
    parts.append("")
    parts.append("# Lint findings inside the changed components")
    for f in findings:
        if inside(f):
            parts.append(json.dumps(_finding_dict(f), default=str))
    parts.append("")
    parts.append(
        "Judge whether this spec change is complete. For each changed "
        "requirement: do its criteria check what it states? Does a "
        "dependent's interface/ need a matching update that was not made? "
        "Does a criterion expect behavior no requirement states?\n"
        "Reply with only the JSON object "
        '{"completeness_score": <number 0.0-1.0>, '
        '"completeness_rationale": "<text>"}.')
    resp = endpoint.complete("\n".join(parts), model, backend=llm_backend)
    data = _reply_data(resp)
    if isinstance(data, dict) and "completeness_score" in data and "completeness_rationale" in data:
        score = data["completeness_score"]
        rationale = data["completeness_rationale"]
        if (isinstance(score, (int, float)) and not isinstance(score, bool)
                and isinstance(rationale, str) and rationale):
            report.completeness_score = min(1.0, max(0.0, float(score)))
            report.completeness_rationale = rationale

    # Redundancy (R-ASSIST-005).
    changed_set = set(changed_reqs)
    unchanged = [rid for rid in reqs if rid not in changed_set]
    texts = {rid: _read(p) for rid, (_s, p) in reqs.items()}
    words = {rid: _words(t) for rid, t in texts.items()}
    pairs = []
    for rid in changed_reqs:
        scored = []
        for oid in unchanged:
            score = _jaccard(words[rid], words[oid])
            if score >= _THRESHOLD:
                scored.append((-score, oid))
        for _neg, oid in sorted(scored)[:_TOP_N]:
            pairs.append((rid, oid))
    if pairs:
        rparts = ["# Candidate requirement pairs", ""]
        for n, (rid, oid) in enumerate(pairs, 1):
            rparts.append(f"## Pair {n}: {rid} / {oid}")
            rparts.append(f"### {rid}")
            rparts.append(texts[rid])
            rparts.append(f"### {oid}")
            rparts.append(texts[oid])
            rparts.append("")
        rparts.append(
            "Which of these pairs describe the same behavior? Reply with only "
            'the JSON object {"redundancy_flags": [{"new_requirement": '
            '"<changed R-id>", "overlaps_with": "<other R-id>", '
            '"rationale": "<text>"}, ...]}, listing only those pairs.')
        resp = endpoint.complete("\n".join(rparts), model, backend=llm_backend)
        data = _reply_data(resp)
        entries = data.get("redundancy_flags") if isinstance(data, dict) else None
        if isinstance(entries, list):
            for e in entries:
                if (isinstance(e, dict) and all(e.get(k) for k in _FLAG_FIELDS)
                        and (e["new_requirement"], e["overlaps_with"]) in pairs):
                    report.redundancy_flags.append({k: e[k] for k in _FLAG_FIELDS})
    return report


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _render_text(d):
    lines = ["lint_findings:"]
    for f in d["lint_findings"]:
        lines.append(f"  {f.get('rule_id')} {f.get('severity')} "
                     f"{f.get('file')}:{f.get('line')} {f.get('message')}")
    if d["halted"]:
        lines.append("halted: true")
    lines.append("predicted_blast_radius:")
    for cid in d["predicted_blast_radius"]:
        review = d["criterion_reviews"].get(cid, {})
        n = len(review.get("findings", []) or [])
        lines.append(f"  {cid}: {n} findings")
    if d["completeness_score"] is not None:
        lines.append(f"completeness_score: {str(d['completeness_score'])}")
        lines.append(f"completeness_rationale: {d['completeness_rationale']}")
    lines.append("redundancy_flags:")
    for e in d["redundancy_flags"]:
        lines.append(f"  {e['new_requirement']} overlaps {e['overlaps_with']}: "
                     f"{e['rationale']}")
    lines.append(f"degraded: {'true' if d['degraded'] else 'false'}")
    return "\n".join(lines)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    flags = ("--changed", "--repo-root", "--format", "--model")
    changed = []
    repo_root = "."
    fmt = "text"
    model = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--") and "=" in tok:
            name, val = tok.split("=", 1)
            if name not in flags:
                return _usage_error(f"unknown argument: {tok}")
        elif tok in flags:
            if i + 1 >= len(argv):
                return _usage_error(f"{tok} requires a value")
            name, val = tok, argv[i + 1]
            i += 1
        else:
            return _usage_error(f"unknown argument: {tok}")
        i += 1
        if name == "--changed":
            changed.extend(p for p in val.split(",") if p)
        elif name == "--repo-root":
            repo_root = val
        elif name == "--format":
            if val not in ("json", "text"):
                return _usage_error(f"invalid --format: {val}")
            fmt = val
        else:
            model = val
    if not changed:
        return _usage_error("--changed is required")
    report = assist(changed, Path(repo_root), model)
    d = report.to_dict()
    if fmt == "json":
        print(json.dumps(d, default=str))
    else:
        print(_render_text(d))
    return 1 if report.halted else 0


if __name__ == "__main__":
    sys.exit(main())
