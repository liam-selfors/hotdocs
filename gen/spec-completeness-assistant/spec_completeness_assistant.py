"""Spec Completeness Assistant: advisory completeness/redundancy checks for a spec change."""

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

_ID_RE = re.compile(r"R-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]+[a-z]?")
_WORD_RE = re.compile(r"[a-z0-9_]{3,}")
_COVERS_RE = re.compile(r"Covers:(.*)")
_THRESHOLD = 0.35
_MAX_CANDIDATES = 5

_USAGE = (
    "usage: hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] "
    "[--format=json|text] [--model=<model>]"
)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_dict(obj):
    if isinstance(obj, dict):
        return obj
    return obj.to_dict()


def _finding_json(finding):
    if isinstance(finding, dict):
        return finding
    out = {k: getattr(finding, k, None) for k in ("rule_id", "severity", "file", "line", "message")}
    if getattr(finding, "rationale", None) is not None:
        out["rationale"] = finding.rationale
    return out


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
            "lint_findings": [_finding_json(f) for f in self.lint_findings],
            "halted": self.halted,
            "predicted_blast_radius": list(self.predicted_blast_radius),
            "criterion_reviews": dict(self.criterion_reviews),
            "completeness_score": self.completeness_score,
            "completeness_rationale": self.completeness_rationale,
            "redundancy_flags": [dict(e) for e in self.redundancy_flags],
            "degraded": self.degraded,
        }


# ---------------------------------------------------------------- loading


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load(slug, repo_root):
    module = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    spec = importlib.util.spec_from_file_location(module, directory / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- corpus


def _resolve_changes(changed_ids, repo_root):
    comps = repo_root / "specs" / "components"
    slugs = []
    reqs = {}
    if not comps.is_dir():
        return slugs, reqs
    dirs = sorted(p for p in comps.iterdir() if p.is_dir())

    def add(slug):
        if slug not in slugs:
            slugs.append(slug)

    for cid in changed_ids:
        if cid.startswith("comp-"):
            d = comps / cid[len("comp-"):]
            if d in dirs:
                add(d.name)
                for r in sorted((d / "requirements").glob("*.md")):
                    reqs.setdefault(r.stem, (d, r))
            continue
        for d in dirs:
            r = d / "requirements" / f"{cid}.md"
            if r.is_file():
                add(d.name)
                reqs.setdefault(cid, (d, r))
                break
            if (d / "acceptance" / f"{cid}.md").is_file():
                add(d.name)
                break
    return slugs, reqs


def _covering(comp_dir, rid):
    out = []
    for a in sorted((comp_dir / "acceptance").glob("*.md")):
        text = a.read_text(encoding="utf-8")
        for line in text.splitlines():
            m = _COVERS_RE.search(line)
            if m and rid in _ID_RE.findall(m.group(1)):
                out.append((a.stem, text))
                break
    return out


def _rel(file, repo_root):
    p = Path(str(file))
    if p.is_absolute():
        try:
            p = p.relative_to(repo_root)
        except ValueError:
            pass
    return p.as_posix()


def _inside(finding, slugs, repo_root):
    rel = _rel(_get(finding, "file"), repo_root)
    return any(rel.startswith(f"specs/components/{slug}/") for slug in slugs)


def _words(text):
    return set(_WORD_RE.findall(_ID_RE.sub("", text).lower()))


def _jaccard(a, b):
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _candidates(reqs, repo_root):
    comps = repo_root / "specs" / "components"
    others = []
    for r in sorted(comps.glob("*/requirements/*.md")):
        if r.stem not in reqs:
            others.append((r.stem, r.read_text(encoding="utf-8")))
    pairs = []
    for rid, (_, path) in reqs.items():
        text = path.read_text(encoding="utf-8")
        words = _words(text)
        scored = []
        for oid, otext in others:
            score = _jaccard(words, _words(otext))
            if score >= _THRESHOLD:
                scored.append((-score, oid, otext))
        scored.sort(key=lambda t: (t[0], t[1]))
        for _, oid, otext in scored[:_MAX_CANDIDATES]:
            pairs.append((rid, text, oid, otext))
    return pairs


# ---------------------------------------------------------------- prompts


def _completeness_prompt(reqs, slugs, criterion_reviews, inside_findings):
    parts = [
        "You are reviewing a spec change for completeness before it is submitted.",
        "",
        "## Changed requirements and their covering acceptance criteria",
        "",
    ]
    for rid, (comp_dir, path) in reqs.items():
        parts.append(f"### Requirement {rid}")
        parts.append(path.read_text(encoding="utf-8"))
        covering = _covering(comp_dir, rid)
        for aid, text in covering:
            parts.append(f"#### Covering criterion {aid}")
            parts.append(text)
        if not covering:
            parts.append(f"No acceptance criterion covers {rid}.")
        parts.append("")
    parts.append("## invisible_reference findings for the changed components")
    for slug in slugs:
        review = criterion_reviews.get(f"comp-{slug}")
        for f in _get(review, "findings") or []:
            if _get(f, "kind") == "invisible_reference":
                parts.append(json.dumps(f, default=str))
    parts.append("")
    parts.append("## Lint findings inside the changed components")
    for f in inside_findings:
        parts.append(json.dumps(_finding_json(f), default=str))
    parts.append("")
    parts.append("## Questions")
    parts.append("1. Do each changed requirement's acceptance criteria check what the requirement states?")
    parts.append(
        "2. Does a dependent component's `interface/` need a matching update that was not made?"
    )
    parts.append("3. Does any criterion expect behavior that no requirement states?")
    parts.append("")
    parts.append(
        "Reply with only a JSON object: "
        '{"completeness_score": <number from 0.0 to 1.0>, "completeness_rationale": "<text>"}'
    )
    return "\n".join(parts)


def _redundancy_prompt(pairs):
    parts = [
        "Each pair below holds a changed requirement and an existing requirement elsewhere "
        "in the spec corpus. Decide which pairs describe the same behavior.",
        "",
    ]
    for rid, text, oid, otext in pairs:
        parts.append(f"## Pair: {rid} / {oid}")
        parts.append(f"### Changed requirement {rid}")
        parts.append(text)
        parts.append(f"### Existing requirement {oid}")
        parts.append(otext)
        parts.append("")
    parts.append(
        "Reply with only a JSON object: "
        '{"redundancy_flags": [{"new_requirement": "<changed R-id>", '
        '"overlaps_with": "<existing R-id>", "rationale": "<text>"}, ...]} '
        "listing only the pairs that describe the same behavior."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------- parsing


def _reply_json(response):
    if _get(response, "model_call_error") is not None:
        return None
    text = _get(response, "text")
    if not isinstance(text, str):
        return None
    lines = text.strip().splitlines()
    if (
        len(lines) >= 2
        and lines[0].strip() in ("```", "```json")
        and lines[-1].strip() == "```"
    ):
        text = "\n".join(lines[1:-1])
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _parse_completeness(response):
    obj = _reply_json(response)
    if obj is None:
        return None, None
    score = obj.get("completeness_score")
    rationale = obj.get("completeness_rationale")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None, None
    if not isinstance(rationale, str) or not rationale:
        return None, None
    return min(max(score, 0.0), 1.0), rationale


def _parse_flags(response, candidate_set):
    obj = _reply_json(response)
    if obj is None:
        return []
    entries = obj.get("redundancy_flags")
    if not isinstance(entries, list):
        return []
    flags = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        values = [entry.get(k) for k in ("new_requirement", "overlaps_with", "rationale")]
        if any(v is None or v == "" for v in values):
            continue
        if (values[0], values[1]) not in candidate_set:
            continue
        flags.append(
            {"new_requirement": values[0], "overlaps_with": values[1], "rationale": values[2]}
        )
    return flags


# ---------------------------------------------------------------- assist


def assist(changed_ids, repo_root, model=None, *, llm_backend=None):
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        return _assist(changed_ids, Path(repo_root), model, llm_backend)
    finally:
        sys.dont_write_bytecode = previous


def _assist(changed_ids, repo_root, model, llm_backend):
    slugs, reqs = _resolve_changes(changed_ids, repo_root)
    degraded = model is None

    reviewer = None
    judge = None
    if not degraded:
        reviewer = _load("spec-reviewer", repo_root)
        judge = reviewer.glossary_judge(model, llm_backend)
    linter = _load("spec-linter", repo_root)
    lint_report = linter.lint(None, repo_root, judge=judge)
    findings = list(_get(lint_report, "findings"))
    inside = [f for f in findings if _inside(f, slugs, repo_root)]

    if any(_get(f, "severity") == "fail" for f in inside):
        return CompletenessReport(
            lint_findings=findings,
            halted=True,
            predicted_blast_radius=[],
            criterion_reviews={},
            completeness_score=None,
            completeness_rationale=None,
            redundancy_flags=[],
            degraded=degraded,
        )

    impact = _load("impact-analyzer", repo_root)
    blast = impact.compute_blast_radius(changed_ids, repo_root)
    if _get(blast, "precondition_error") is None:
        predicted = [_get(e, "component_id") for e in _get(blast, "impacted")]
    else:
        predicted = []

    reviews = {}
    if predicted and reviewer is None:
        reviewer = _load("spec-reviewer", repo_root)
    for component_id in predicted:
        try:
            reviews[component_id] = _to_dict(reviewer.check([component_id], repo_root))
        except Exception as exc:  # noqa: BLE001 - R-ASSIST-003 records any failure
            reviews[component_id] = {"error": str(exc)}

    report = CompletenessReport(
        lint_findings=findings,
        halted=False,
        predicted_blast_radius=predicted,
        criterion_reviews=reviews,
        completeness_score=None,
        completeness_rationale=None,
        redundancy_flags=[],
        degraded=degraded,
    )
    if degraded:
        return report

    endpoint = _load("llm-endpoint", repo_root)
    prompt = _completeness_prompt(reqs, slugs, reviews, inside)
    response = endpoint.complete(prompt, model, backend=llm_backend)
    report.completeness_score, report.completeness_rationale = _parse_completeness(response)

    pairs = _candidates(reqs, repo_root)
    if pairs:
        candidate_set = {(p[0], p[2]) for p in pairs}
        response = endpoint.complete(_redundancy_prompt(pairs), model, backend=llm_backend)
        report.redundancy_flags = _parse_flags(response, candidate_set)
    return report


# ---------------------------------------------------------------- CLI


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def _render_text(data):
    lines = ["lint findings:"]
    for f in data["lint_findings"]:
        lines.append(
            f"  {_get(f, 'rule_id')} {_get(f, 'severity')} "
            f"{_get(f, 'file')}:{_get(f, 'line')} {_get(f, 'message')}"
        )
    lines.append(f"halted: {str(data['halted']).lower()}")
    lines.append("predicted blast radius:")
    for component_id in data["predicted_blast_radius"]:
        review = data["criterion_reviews"].get(component_id)
        count = len(_get(review, "findings") or [])
        lines.append(f"  {component_id}: {count} criterion review findings")
    if data["completeness_score"] is not None:
        lines.append(f"completeness_score: {str(data['completeness_score'])}")
        lines.append(f"completeness_rationale: {data['completeness_rationale']}")
    lines.append("redundancy flags:")
    for e in data["redundancy_flags"]:
        lines.append(f"  {e['new_requirement']} overlaps {e['overlaps_with']}: {e['rationale']}")
    lines.append(f"degraded: {str(data['degraded']).lower()}")
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
        token = argv[i]
        name, eq, value = token.partition("=")
        if name not in flags:
            return _usage_error(f"unknown argument: {token}")
        if not eq:
            if i + 1 >= len(argv):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = argv[i]
        i += 1
        if name == "--changed":
            changed.extend(v for v in value.split(",") if v)
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
    data = report.to_dict()
    if fmt == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        print(_render_text(data))
    return 1 if report.halted else 0
