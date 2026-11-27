"""Spec Completeness Assistant: advisory completeness preview for a spec change."""

import importlib.util
import itertools
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = (
    "usage: hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] "
    "[--format=json|text] [--model=<model>]"
)

_RID = r"R-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]+[a-z]?"
_RID_RE = re.compile(_RID)
_WORD_RE = re.compile(r"[a-z0-9_]{3,}")
_THRESHOLD = 0.35
_TOP_N = 5
_FINDING_FIELDS = ("rule_id", "severity", "file", "line", "message")

_LOAD_COUNTER = itertools.count()


@dataclass
class CompletenessReport:
    lint_findings: list = field(default_factory=list)
    halted: bool = False
    predicted_blast_radius: list = field(default_factory=list)
    criterion_reviews: dict = field(default_factory=dict)
    completeness_score: object = None
    completeness_rationale: object = None
    redundancy_flags: list = field(default_factory=list)
    degraded: bool = False

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
        return dict(finding)
    out = {k: _get(finding, k) for k in _FINDING_FIELDS}
    rationale = _get(finding, "rationale")
    if rationale is not None:
        out["rationale"] = rationale
    return out


# ---------------------------------------------------------------- loading


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load(repo_root, slug, module):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module}.py"
    name = f"_spec_completeness_assistant_dep_{module}_{next(_LOAD_COUNTER)}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- corpus


def _component_dirs(repo_root):
    root = Path(repo_root) / "specs" / "components"
    if not root.is_dir():
        return {}
    return {p.name: p for p in sorted(root.iterdir()) if p.is_dir()}


def _requirement_files(comp_dir):
    return sorted((comp_dir / "requirements").glob("R-*.md"))


def _resolve_changed(changed_ids, dirs):
    comps = []
    reqs = []
    for cid in changed_ids:
        if cid.startswith("comp-"):
            slug = cid[len("comp-"):]
            if slug in dirs:
                if slug not in comps:
                    comps.append(slug)
                for req in _requirement_files(dirs[slug]):
                    if req not in reqs:
                        reqs.append(req)
            continue
        for slug, comp_dir in dirs.items():
            rq = comp_dir / "requirements" / f"{cid}.md"
            ac = comp_dir / "acceptance" / f"{cid}.md"
            if rq.is_file() or ac.is_file():
                if slug not in comps:
                    comps.append(slug)
            if rq.is_file() and rq not in reqs:
                reqs.append(rq)
    return comps, reqs


def _read(path):
    return path.read_text(encoding="utf-8")


def _covering_criteria(req_path):
    rid = req_path.stem
    out = []
    for crit in sorted((req_path.parent.parent / "acceptance").glob("*.md")):
        text = _read(crit)
        for line in text.splitlines():
            if "Covers:" in line:
                ids = _RID_RE.findall(line.split("Covers:", 1)[1])
                if rid in ids:
                    out.append((crit, text))
                    break
    return out


def _inside(finding, repo_root, comps):
    rel = str(_get(finding, "file"))
    if os.path.isabs(rel):
        rel = os.path.relpath(rel, str(repo_root))
    rel = rel.replace(os.sep, "/")
    return any(rel.startswith(f"specs/components/{slug}/") for slug in comps)


# ---------------------------------------------------------------- redundancy


def _words(text):
    return set(_WORD_RE.findall(_RID_RE.sub("", text).lower()))


def _jaccard(a, b):
    if a == b:
        return 1.0
    return len(a & b) / len(a | b)


def _candidates(changed_reqs, dirs):
    changed_set = set(changed_reqs)
    others = []
    for comp_dir in dirs.values():
        for req in _requirement_files(comp_dir):
            if req not in changed_set:
                text = _read(req)
                others.append((req.stem, text, _words(text)))
    pairs = []
    for req in changed_reqs:
        text = _read(req)
        words = _words(text)
        scored = []
        for oid, otext, owords in others:
            score = _jaccard(words, owords)
            if score >= _THRESHOLD:
                scored.append((-score, oid, otext))
        scored.sort(key=lambda s: (s[0], s[1]))
        for _, oid, otext in scored[:_TOP_N]:
            pairs.append((req.stem, text, oid, otext))
    return pairs


# ---------------------------------------------------------------- model replies


def _parse_json(text):
    s = text.strip()
    lines = s.splitlines()
    if (
        len(lines) >= 2
        and lines[0].rstrip() in ("```", "```json")
        and lines[-1].strip() == "```"
    ):
        s = "\n".join(lines[1:-1])
    try:
        return json.loads(s)
    except ValueError:
        return None


def _reply_json(resp):
    if _get(resp, "model_call_error") is not None:
        return None
    return _parse_json(_get(resp, "text"))


def _parse_completeness(resp):
    parsed = _reply_json(resp)
    if not isinstance(parsed, dict):
        return None, None
    score = parsed.get("completeness_score")
    rationale = parsed.get("completeness_rationale")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None, None
    if not (isinstance(rationale, str) and rationale):
        return None, None
    return min(1.0, max(0.0, float(score))), rationale


def _parse_redundancy(resp, candidate_keys):
    parsed = _reply_json(resp)
    if not isinstance(parsed, dict):
        return []
    entries = parsed.get("redundancy_flags")
    if not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        vals = [entry.get(k) for k in ("new_requirement", "overlaps_with", "rationale")]
        if not all(isinstance(v, str) and v for v in vals):
            continue
        if (vals[0], vals[1]) not in candidate_keys:
            continue
        out.append(
            {"new_requirement": vals[0], "overlaps_with": vals[1], "rationale": vals[2]}
        )
    return out


# ---------------------------------------------------------------- prompts


def _completeness_prompt(changed_reqs, comps, criterion_reviews, inside_findings):
    parts = [
        "You are reviewing a spec change for completeness before it is submitted.",
        "",
        "For each changed requirement below, judge: whether its acceptance "
        "criteria check what it states; whether a dependent component's "
        "`interface/` needs a matching update that was not made; and whether "
        "a criterion expects behavior no requirement states.",
        "",
    ]
    for req in changed_reqs:
        rid = req.stem
        parts.append(f"## Changed requirement {rid}")
        parts.append("")
        parts.append(_read(req))
        parts.append("")
        covering = _covering_criteria(req)
        if not covering:
            parts.append(f"No acceptance criterion covers {rid}.")
            parts.append("")
        for crit, text in covering:
            parts.append(f"### Covering criterion {crit.stem}")
            parts.append("")
            parts.append(text)
            parts.append("")
    parts.append("## invisible_reference findings for the changed components")
    parts.append("")
    for slug in comps:
        review = criterion_reviews.get(f"comp-{slug}", {})
        for finding in review.get("findings", []):
            if _get(finding, "kind") == "invisible_reference":
                parts.append(json.dumps(finding, default=str))
    parts.append("")
    parts.append("## Lint findings inside the changed components")
    parts.append("")
    for finding in inside_findings:
        parts.append(json.dumps(_finding_dict(finding), default=str))
    parts.append("")
    parts.append(
        "Reply with only a JSON object: "
        '{"completeness_score": <number from 0.0 to 1.0>, '
        '"completeness_rationale": "<text>"}'
    )
    return "\n".join(parts)


def _redundancy_prompt(pairs):
    parts = [
        "Each pair below holds a changed requirement and an existing requirement "
        "elsewhere in the spec corpus. Decide which pairs describe the same behavior.",
        "",
    ]
    for new_id, new_text, old_id, old_text in pairs:
        parts.append(f"## Pair: {new_id} / {old_id}")
        parts.append("")
        parts.append(f"### {new_id}")
        parts.append("")
        parts.append(new_text)
        parts.append("")
        parts.append(f"### {old_id}")
        parts.append("")
        parts.append(old_text)
        parts.append("")
    parts.append(
        "Reply with only a JSON object: "
        '{"redundancy_flags": [{"new_requirement": "<changed R-id>", '
        '"overlaps_with": "<existing R-id>", "rationale": "<text>"}, ...]} '
        "listing only the pairs that describe the same behavior."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------- assist


def assist(changed_ids, repo_root, model=None, *, llm_backend=None):
    deps = {}

    def dep(slug, module):
        if module not in deps:
            deps[module] = _load(repo_root, slug, module)
        return deps[module]

    dirs = _component_dirs(repo_root)
    comps, changed_reqs = _resolve_changed(changed_ids, dirs)

    judge = None
    if model is not None:
        judge = dep("spec-reviewer", "spec_reviewer").glossary_judge(model, llm_backend)

    lint_report = dep("spec-linter", "spec_linter").lint(None, repo_root, judge=judge)
    lint_findings = list(_get(lint_report, "findings"))
    inside_findings = [f for f in lint_findings if _inside(f, repo_root, comps)]
    halted = any(_get(f, "severity") == "fail" for f in inside_findings)

    report = CompletenessReport(
        lint_findings=lint_findings, halted=halted, degraded=model is None
    )
    if halted:
        return report

    blast = dep("impact-analyzer", "impact_analyzer").compute_blast_radius(
        changed_ids, repo_root
    )
    if _get(blast, "precondition_error") is None:
        report.predicted_blast_radius = [
            _get(entry, "component_id") for entry in _get(blast, "impacted")
        ]

    reviewer = dep("spec-reviewer", "spec_reviewer")
    for cid in report.predicted_blast_radius:
        try:
            review = reviewer.check([cid], repo_root)
            report.criterion_reviews[cid] = (
                review if isinstance(review, dict) else review.to_dict()
            )
        except Exception as exc:
            report.criterion_reviews[cid] = {"error": str(exc)}

    if model is None:
        return report

    llm = dep("llm-endpoint", "llm_endpoint")
    prompt = _completeness_prompt(
        changed_reqs, comps, report.criterion_reviews, inside_findings
    )
    resp = llm.complete(prompt, model, backend=llm_backend)
    report.completeness_score, report.completeness_rationale = _parse_completeness(resp)

    pairs = _candidates(changed_reqs, dirs)
    if pairs:
        keys = {(p[0], p[2]) for p in pairs}
        resp = llm.complete(_redundancy_prompt(pairs), model, backend=llm_backend)
        report.redundancy_flags = _parse_redundancy(resp, keys)

    return report


# ---------------------------------------------------------------- CLI


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _render_text(report):
    lines = []
    for finding in report.lint_findings:
        lines.append(
            f"lint: {_get(finding, 'rule_id')} {_get(finding, 'severity')} "
            f"{_get(finding, 'file')}:{_get(finding, 'line')}: {_get(finding, 'message')}"
        )
    if report.halted:
        lines.append("halted: a fail finding lies inside a changed component")
    for cid in report.predicted_blast_radius:
        review = report.criterion_reviews.get(cid, {})
        lines.append(f"{cid}: {len(review.get('findings', []))} findings")
    if report.completeness_score is not None:
        lines.append(f"completeness_score: {report.completeness_score}")
        lines.append(f"completeness_rationale: {report.completeness_rationale}")
    for entry in report.redundancy_flags:
        lines.append(
            f"redundancy: {entry['new_requirement']} overlaps {entry['overlaps_with']}: "
            f"{entry['rationale']}"
        )
    if report.degraded:
        lines.append("degraded: no model configured")
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
        name, eq, value = tok.partition("=")
        if name not in flags:
            return _usage_error(f"unknown argument: {tok}")
        if not eq:
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
            if value not in ("json", "text"):
                return _usage_error(f"invalid --format: {value}")
            fmt = value
        else:
            model = value
    if not changed:
        return _usage_error("--changed is required")

    report = assist(changed, Path(repo_root), model)
    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(_render_text(report))
    return 1 if report.halted else 0
