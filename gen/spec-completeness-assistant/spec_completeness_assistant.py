"""Spec Completeness Assistant: advisory, feature-branch-side completeness checks.

Never a gate: `assist` only returns a `CompletenessReport`; nothing here
blocks, fails or writes anything under `repo_root`.
"""

import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_USAGE = (
    "usage: hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] "
    "[--format=json|text] [--model=<model>]"
)

_ID_RE = re.compile(r"R-[A-Z0-9]+(-[A-Z0-9]+)*-[0-9]+[a-z]?")
_WORD_RE = re.compile(r"[a-z0-9_]{3,}")
_JACCARD_MIN = 0.35
_TOP_CANDIDATES = 5
_FINDING_FIELDS = ("rule_id", "severity", "file", "line", "message")
_FLAG_FIELDS = ("new_requirement", "overlaps_with", "rationale")


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


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _finding_dict(finding):
    if isinstance(finding, dict):
        return finding
    out = {k: _get(finding, k) for k in _FINDING_FIELDS}
    rationale = _get(finding, "rationale")
    if rationale is not None:
        out["rationale"] = rationale
    return out


def _tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load(repo_root, slug, module):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    spec = importlib.util.spec_from_file_location(module, base / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    return path.read_text(encoding="utf-8")


def _covered_ids(text):
    ids = set()
    for line in text.splitlines():
        if "Covers:" in line:
            rest = line.split("Covers:", 1)[1]
            ids.update(m.group(0) for m in _ID_RE.finditer(rest))
    return ids


def _changed(root, changed_ids):
    comps_dir = root / "specs" / "components"
    slugs = {}
    reqs = {}
    for cid in changed_ids:
        if cid.startswith("comp-"):
            slug = cid[len("comp-"):]
            d = comps_dir / slug
            if d.is_dir():
                slugs[slug] = None
                for p in sorted((d / "requirements").glob("*.md")):
                    reqs.setdefault(p.stem, (p, slug))
        else:
            for kind in ("requirements", "acceptance"):
                for p in sorted(comps_dir.glob(f"*/{kind}/{cid}.md")):
                    slug = p.parent.parent.name
                    slugs[slug] = None
                    if kind == "requirements":
                        reqs.setdefault(cid, (p, slug))
    return list(slugs), reqs


def _inside(finding, root, slugs):
    rel = os.path.relpath(root / str(_get(finding, "file")), root).replace(os.sep, "/")
    return any(rel.startswith(f"specs/components/{s}/") for s in slugs)


def _words(text):
    return set(_WORD_RE.findall(_ID_RE.sub("", text).lower()))


def _jaccard(a, b):
    return 1.0 if a == b else len(a & b) / len(a | b)


def _unwrap(text):
    s = text.strip()
    lines = s.split("\n")
    if (
        len(lines) >= 2
        and lines[0].strip() in ("```", "```json")
        and lines[-1].strip() == "```"
    ):
        s = "\n".join(lines[1:-1])
    return s


def _parse_reply(resp):
    if _get(resp, "model_call_error") is not None:
        return None
    try:
        return json.loads(_unwrap(_get(resp, "text")))
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_completeness(resp):
    obj = _parse_reply(resp)
    if not isinstance(obj, dict):
        return None, None
    score = obj.get("completeness_score")
    rationale = obj.get("completeness_rationale")
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not isinstance(rationale, str)
        or not rationale
    ):
        return None, None
    return min(1.0, max(0.0, float(score))), rationale


def _parse_redundancy(resp, candidates):
    obj = _parse_reply(resp)
    if not isinstance(obj, dict) or not isinstance(obj.get("redundancy_flags"), list):
        return []
    flags = []
    for entry in obj["redundancy_flags"]:
        if not isinstance(entry, dict):
            continue
        if not all(isinstance(entry.get(k), str) and entry.get(k) for k in _FLAG_FIELDS):
            continue
        if (entry["new_requirement"], entry["overlaps_with"]) not in candidates:
            continue
        flags.append({k: entry[k] for k in _FLAG_FIELDS})
    return flags


def _render_finding(f):
    return (
        f"{_get(f, 'file')}:{_get(f, 'line')}: {_get(f, 'rule_id')} "
        f"({_get(f, 'severity')}): {_get(f, 'message')}"
    )


def _completeness_prompt(root, slugs, reqs, reviews, lint_findings):
    comps_dir = root / "specs" / "components"
    parts = [
        "You are reviewing a proposed spec change for completeness.",
        "For each changed requirement below, judge whether its acceptance "
        "criteria check what it states; whether a dependent component's "
        "interface/ needs a matching update that was not made; and whether "
        "any criterion expects behavior no requirement states.",
        'Reply with only the JSON object {"completeness_score": <0.0-1.0>, '
        '"completeness_rationale": "<text>"}.',
        "",
        "## Changed requirements",
    ]
    for rid, (path, slug) in reqs.items():
        parts.append(_read(path))
        criteria = [
            p
            for p in sorted((comps_dir / slug / "acceptance").glob("*.md"))
            if rid in _covered_ids(_read(p))
        ]
        for p in criteria:
            parts.append(_read(p))
        if not criteria:
            parts.append(f"No acceptance criterion covers {rid}.")
    parts.append("")
    parts.append("## Invisible-reference findings")
    for slug in slugs:
        review = reviews.get(f"comp-{slug}", {})
        for f in _get(review, "findings") or []:
            if _get(f, "kind") == "invisible_reference":
                parts.append(f"{_get(f, 'criterion_id')}: {_get(f, 'message')}")
    parts.append("")
    parts.append("## Lint findings in changed components")
    for f in lint_findings:
        if _inside(f, root, slugs):
            parts.append(_render_finding(f))
    return "\n".join(parts)


def _redundancy_candidates(root, reqs):
    comps_dir = root / "specs" / "components"
    others = [
        (p.stem, _read(p))
        for p in sorted(comps_dir.glob("*/requirements/*.md"))
        if p.stem not in reqs
    ]
    other_words = [(oid, text, _words(text)) for oid, text in others]
    pairs = []
    for rid, (path, _slug) in reqs.items():
        text = _read(path)
        words = _words(text)
        scored = []
        for oid, otext, owords in other_words:
            score = _jaccard(words, owords)
            if score >= _JACCARD_MIN:
                scored.append((-score, oid, otext))
        scored.sort(key=lambda t: (t[0], t[1]))
        for _neg, oid, otext in scored[:_TOP_CANDIDATES]:
            pairs.append((rid, text, oid, otext))
    return pairs


def _redundancy_prompt(pairs):
    parts = [
        "Each pair below holds a newly changed requirement and an existing "
        "requirement elsewhere in the spec corpus. Say which pairs describe "
        "the same behavior.",
        'Reply with only the JSON object {"redundancy_flags": [{"new_requirement": '
        '"<R-id>", "overlaps_with": "<R-id>", "rationale": "<text>"}, ...]}.',
    ]
    for rid, text, oid, otext in pairs:
        parts.append("")
        parts.append(f"## Pair: {rid} / {oid}")
        parts.append(f"### {rid}")
        parts.append(text)
        parts.append(f"### {oid}")
        parts.append(otext)
    return "\n".join(parts)


def assist(changed_ids, repo_root, model=None, *, llm_backend=None):
    root = Path(repo_root)
    judge = None
    if model is not None:
        reviewer = _load(repo_root, "spec-reviewer", "spec_reviewer")
        judge = reviewer.glossary_judge(model, llm_backend)

    linter = _load(repo_root, "spec-linter", "spec_linter")
    lint_report = linter.lint(None, repo_root, judge=judge)
    lint_findings = list(_get(lint_report, "findings") or [])

    slugs, reqs = _changed(root, changed_ids)
    degraded = model is None

    if any(
        _get(f, "severity") == "fail" and _inside(f, root, slugs) for f in lint_findings
    ):
        return CompletenessReport(
            lint_findings=lint_findings,
            halted=True,
            predicted_blast_radius=[],
            criterion_reviews={},
            completeness_score=None,
            completeness_rationale=None,
            redundancy_flags=[],
            degraded=degraded,
        )

    impact = _load(repo_root, "impact-analyzer", "impact_analyzer")
    blast = impact.compute_blast_radius(changed_ids, repo_root)
    if _get(blast, "precondition_error") is not None:
        radius = []
    else:
        radius = [_get(e, "component_id") for e in _get(blast, "impacted") or []]

    reviewer = _load(repo_root, "spec-reviewer", "spec_reviewer")
    reviews = {}
    for cid in radius:
        try:
            reviews[cid] = reviewer.check([cid], repo_root).to_dict()
        except Exception as exc:  # noqa: BLE001 - a failing check is recorded, not raised
            reviews[cid] = {"error": str(exc)}

    report = CompletenessReport(
        lint_findings=lint_findings,
        halted=False,
        predicted_blast_radius=radius,
        criterion_reviews=reviews,
        completeness_score=None,
        completeness_rationale=None,
        redundancy_flags=[],
        degraded=degraded,
    )
    if model is None:
        return report

    endpoint = _load(repo_root, "llm-endpoint", "llm_endpoint")
    prompt = _completeness_prompt(root, slugs, reqs, reviews, lint_findings)
    resp = endpoint.complete(prompt, model, backend=llm_backend)
    report.completeness_score, report.completeness_rationale = _parse_completeness(resp)

    pairs = _redundancy_candidates(root, reqs)
    if pairs:
        candidates = {(rid, oid) for rid, _t, oid, _o in pairs}
        resp = endpoint.complete(_redundancy_prompt(pairs), model, backend=llm_backend)
        report.redundancy_flags = _parse_redundancy(resp, candidates)
    return report


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def _render_text(report):
    lines = ["lint findings:"]
    for f in report.lint_findings:
        lines.append(f"  {_get(f, 'rule_id')} {_render_finding(f)}")
    lines.append(f"halted: {report.halted}")
    lines.append("predicted blast radius:")
    for cid in report.predicted_blast_radius:
        review = report.criterion_reviews.get(cid, {})
        count = len(_get(review, "findings") or [])
        lines.append(f"  {cid}: {count} criterion review findings")
    if report.completeness_score is not None:
        lines.append(f"completeness_score: {report.completeness_score}")
        lines.append(f"completeness_rationale: {report.completeness_rationale}")
    for e in report.redundancy_flags:
        lines.append(
            f"redundancy: {e['new_requirement']} overlaps {e['overlaps_with']}: "
            f"{e['rationale']}"
        )
    lines.append(f"degraded: {report.degraded}")
    return "\n".join(lines)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    flags = ("--changed", "--repo-root", "--format", "--model")
    changed = []
    repo_root = None
    fmt = "text"
    model = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        name, sep, value = tok.partition("=")
        if name not in flags:
            return _usage_error(f"unknown argument: {tok}")
        if not sep:
            if i + 1 >= len(argv):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = argv[i]
        i += 1
        if name == "--changed":
            changed.extend(p for p in value.split(",") if p)
        elif name == "--repo-root":
            repo_root = value
        elif name == "--format":
            fmt = value
        else:
            model = value
    if not changed:
        return _usage_error("--changed is required")
    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format: {fmt}")

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    report = assist(changed, root, model)
    if fmt == "json":
        print(json.dumps(report.to_dict()))
    else:
        print(_render_text(report))
    return 1 if report.halted else 0


if __name__ == "__main__":
    sys.exit(main())
