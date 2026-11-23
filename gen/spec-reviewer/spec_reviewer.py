"""Spec Reviewer: checks whether each acceptance criterion can be implemented
from what its test author sees, and proposes spec text closing each gap.

Advisory only.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = (
    "usage: hotdocs spec check <target>... [--model=<model>] [--write-proposals] "
    "[--strict] [--format=json|text] [--repo-root=<dir>]"
)

D361_SENTENCE = (
    "The pipeline fixes the test framework (pytest), the test file's name and "
    "location, and how the test reaches the component's code: never report any "
    "of these as a gap."
)

GAP_KINDS = ("guess", "unstated_behavior")
UNPARSEABLE_MESSAGE = "reply was not the JSON object asked for"
_TOKEN_RE = re.compile(r"`([^`]*)`")


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


@dataclass
class ReviewReport:
    targets: list = field(default_factory=list)
    criteria_checked: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    writable: dict = field(default_factory=dict)
    lint_findings: list = field(default_factory=list)
    proposals: list = field(default_factory=list)
    degraded: bool = False

    def _keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def keys(self):
        return self._keys()

    def __getitem__(self, key):
        if key not in self._keys():
            raise KeyError(key)
        return getattr(self, key)

    def __contains__(self, key):
        return key in self._keys()

    def __iter__(self):
        return iter(self._keys())

    def __len__(self):
        return len(self._keys())

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self):
        return dataclasses.asdict(self)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _as_dict(obj):
    if isinstance(obj, dict):
        return dict(obj)
    if dataclasses.is_dataclass(obj):
        return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}
    return dict(vars(obj))


def _tool_root():
    here = Path(__file__).resolve()
    return next(d.parent for d in here.parents if d.name == "gen")


def _load_from(base, module):
    path = base / f"{module}.py"
    spec = importlib.util.spec_from_file_location(module, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _load(repo_root, slug, module):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    return _load_from(base, module)


def _extract_object(text):
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


# --------------------------------------------------------------------------
# Glossary judge (R-REVIEW-006)
# --------------------------------------------------------------------------


def _make_judge(model, llm_backend, complete):
    def judge(term, local_text, glossary_text):
        prompt = (
            "You judge whether a component's local definition of a term "
            "conflicts with the glossary's definition of it.\n\n"
            f"Term: {term}\n\n"
            f"Local definition:\n{local_text}\n\n"
            f"Glossary definition:\n{glossary_text}\n\n"
            'Reply with one JSON object: {"conflicts": <bool>, "rationale": "<text>"}'
        )
        response = complete(prompt, model, backend=llm_backend)
        if _get(response, "model_call_error"):
            return None
        obj = _extract_object(_get(response, "text") or "")
        if obj is None:
            return None
        conflicts = obj.get("conflicts")
        rationale = obj.get("rationale")
        if not isinstance(conflicts, bool) or not isinstance(rationale, str):
            return None
        return (conflicts, rationale)

    return judge


def glossary_judge(model, llm_backend=None):
    endpoint = _load_from(_tool_root() / "gen" / "llm-endpoint", "llm_endpoint")
    return _make_judge(model, llm_backend, endpoint.complete)


# --------------------------------------------------------------------------
# Target resolution (R-REVIEW-001)
# --------------------------------------------------------------------------


def _resolve_targets(targets, repo_root):
    components_dir = repo_root / "specs" / "components"
    criteria = {}
    slugs = set()
    for target in targets:
        if target.startswith("comp-") and (components_dir / target[len("comp-"):]).is_dir():
            slug = target[len("comp-"):]
            slugs.add(slug)
            for path in (components_dir / slug / "acceptance").glob("AC-*.md"):
                criteria[path.stem] = slug
            continue
        matches = sorted(components_dir.glob(f"*/acceptance/{target}.md"))
        if not matches:
            raise ValueError(f"unknown target id: {target}")
        slug = matches[0].parent.parent.name
        slugs.add(slug)
        criteria[target] = slug
    return criteria, sorted(slugs)


# --------------------------------------------------------------------------
# Asset interface check (R-REVIEW-008)
# --------------------------------------------------------------------------


def _assets(component_md):
    lines = component_md.read_text(encoding="utf-8").splitlines()
    marks = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(marks) < 2:
        return []
    for line in lines[marks[0] + 1:marks[1]]:
        if line.startswith("assets:"):
            if "[" not in line:
                return []
            inner = line.split("[", 1)[1].split("]", 1)[0]
            result = []
            for item in inner.split(","):
                item = item.strip()
                if ":" not in item:
                    continue
                kind, path = item.split(":", 1)
                result.append((kind.strip(), path.strip()))
            return result
    return []


def _asset_findings(slugs, repo_root):
    findings = []
    for slug in sorted(slugs, key=lambda s: f"comp-{s}"):
        comp_dir = repo_root / "specs" / "components" / slug
        for _kind, path in _assets(comp_dir / "component.md"):
            file_name = path.rsplit("/", 1)[-1]
            rel = f"specs/components/{slug}/interface/assets/{file_name}.md"
            if not (repo_root / rel).exists():
                findings.append({
                    "criterion_id": f"comp-{slug}",
                    "kind": "asset_interface_missing",
                    "token": path,
                    "message": f"`{path}` has no interface file {rel}",
                })
    return findings


# --------------------------------------------------------------------------
# Invisible reference check (R-REVIEW-003)
# --------------------------------------------------------------------------


def _step_tokens(criterion_text):
    tokens = []
    inside = False
    step = None
    for line in criterion_text.splitlines():
        if not inside:
            if line.strip() == "```gherkin":
                inside = True
            continue
        if line.strip().startswith("```"):
            break
        words = line.split()
        if words and words[0] in ("Given", "When", "Then"):
            step = words[0]
        if step in ("When", "Then"):
            for raw in _TOKEN_RE.findall(line):
                token = raw.strip().split("<", 1)[0]
                if token and token not in tokens:
                    tokens.append(token)
    return tokens


def _visible_text(bundle):
    parts = [
        _get(bundle, "requirement_text") or "",
        _get(bundle, "interface") or "",
        _get(bundle, "glossary") or "",
    ]
    parts.extend((_get(bundle, "dependency_interfaces") or {}).values())
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Model review (R-REVIEW-004)
# --------------------------------------------------------------------------


def _criterion_prompt(bundle):
    deps = _get(bundle, "dependency_interfaces") or {}
    dep_text = "\n\n".join(f"### {cid}\n{text}" for cid, text in deps.items())
    return (
        "You are the author of the executable test for one acceptance criterion. "
        "You see only the material below. Say whether you could write that test "
        "from it alone, what you would have to guess, and what behavior the "
        "criterion checks that no requirement or interface text states.\n\n"
        f"{D361_SENTENCE}\n\n"
        f"## component_id\n{_get(bundle, 'component_id')}\n\n"
        f"## criterion_id\n{_get(bundle, 'criterion_id')}\n\n"
        f"## covers\n{_get(bundle, 'covers')}\n\n"
        f"## CRITERION\n{_get(bundle, 'criterion_text')}\n\n"
        f"## REQUIREMENT\n{_get(bundle, 'requirement_text')}\n\n"
        f"## INTERFACE\n{_get(bundle, 'interface')}\n\n"
        f"## GLOSSARY\n{_get(bundle, 'glossary')}\n\n"
        f"## DEPENDENCY INTERFACES\n{dep_text}\n\n"
        f"## TESTING\n{_get(bundle, 'testing') or ''}\n\n"
        "Reply with one JSON object:\n"
        '{"writable": <bool>,\n'
        ' "gaps": [{"kind": "guess" | "unstated_behavior", "missing": "<text>",\n'
        '           "proposed_text": "<text>", "target_file": "<path>"}]}\n'
    )


def _review_with_model(criterion_id, bundle, model, llm_backend, complete):
    """Return (writable, gaps, finding_or_None)."""
    response = complete(_criterion_prompt(bundle), model, backend=llm_backend)
    error = _get(response, "model_call_error")
    if error:
        return None, [], {
            "criterion_id": criterion_id,
            "kind": "model_unparseable",
            "token": "",
            "message": _get(error, "message"),
        }
    obj = _extract_object(_get(response, "text") or "")
    if obj is None or not isinstance(obj.get("writable"), bool):
        return None, [], {
            "criterion_id": criterion_id,
            "kind": "model_unparseable",
            "token": "",
            "message": UNPARSEABLE_MESSAGE,
        }
    gaps = []
    for gap in obj.get("gaps") or []:
        if isinstance(gap, dict) and gap.get("kind") in GAP_KINDS:
            gaps.append({
                "criterion_id": criterion_id,
                "kind": gap["kind"],
                "missing": gap.get("missing", ""),
                "proposed_text": gap.get("proposed_text", ""),
                "target_file": gap.get("target_file", ""),
            })
    return obj["writable"], gaps, None


# --------------------------------------------------------------------------
# Proposals (R-REVIEW-005)
# --------------------------------------------------------------------------


def _write_proposals(gaps, criteria_checked, repo_root):
    written = []
    out_dir = repo_root / ".hotdocs" / "proposals"
    for criterion_id in criteria_checked:
        own = [g for g in gaps if g["criterion_id"] == criterion_id]
        if not own:
            continue
        lines = [f"# Proposals for {criterion_id}"]
        for gap in own:
            lines.extend([
                "",
                f"- kind: {gap['kind']}",
                f"  missing: {gap['missing']}",
                f"  target_file: {gap['target_file']}",
                f"  proposed_text: {gap['proposed_text']}",
            ])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{criterion_id}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(f".hotdocs/proposals/{criterion_id}.md")
    return written


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------


def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):
    repo_root = Path(repo_root)
    criteria, slugs = _resolve_targets(targets, repo_root)

    findings = _asset_findings(slugs, repo_root)

    linter = _load(repo_root, "spec-linter", "spec_linter")
    complete = None
    judge = None
    if model:
        endpoint = _load(repo_root, "llm-endpoint", "llm_endpoint")
        complete = endpoint.complete
        judge = _make_judge(model, llm_backend, complete)

    paths = [repo_root / "specs" / "components" / slug for slug in slugs]
    lint_report = linter.lint(paths, repo_root, judge=judge)
    lint_findings = [_as_dict(f) for f in (_get(lint_report, "findings") or [])]

    if any(f.get("severity") == "fail" for f in lint_findings):
        return ReviewReport(
            targets=list(targets),
            criteria_checked=[],
            findings=findings,
            gaps=[],
            writable={},
            lint_findings=lint_findings,
            proposals=[],
            degraded=not model,
        )

    assembler = _load(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
    criteria_checked = sorted(criteria)
    gaps = []
    writable = {}
    for criterion_id in criteria_checked:
        component_id = f"comp-{criteria[criterion_id]}"
        bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
        visible = _visible_text(bundle)
        for token in _step_tokens(_get(bundle, "criterion_text") or ""):
            if token not in visible:
                findings.append({
                    "criterion_id": criterion_id,
                    "kind": "invisible_reference",
                    "token": token,
                    "message": (
                        f"`{token}` appears in {criterion_id} but not in what "
                        "its test author sees"
                    ),
                })
        if model:
            verdict, own_gaps, finding = _review_with_model(
                criterion_id, bundle, model, llm_backend, complete
            )
            writable[criterion_id] = verdict
            gaps.extend(own_gaps)
            if finding is not None:
                findings.append(finding)
        else:
            writable[criterion_id] = None

    proposals = []
    if write_proposals and gaps:
        proposals = _write_proposals(gaps, criteria_checked, repo_root)

    return ReviewReport(
        targets=list(targets),
        criteria_checked=criteria_checked,
        findings=findings,
        gaps=gaps,
        writable=writable,
        lint_findings=lint_findings,
        proposals=proposals,
        degraded=not model,
    )


# --------------------------------------------------------------------------
# CLI (R-REVIEW-007)
# --------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _parse(argv):
    opts = {"model": None, "format": "text", "repo-root": ".",
            "write-proposals": False, "strict": False, "targets": []}
    i = 0
    while i < len(argv):
        token = argv[i]
        name = token.split("=", 1)[0]
        if name in ("--model", "--format", "--repo-root"):
            if "=" in token:
                value = token.split("=", 1)[1]
            else:
                if i + 1 >= len(argv):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                value = argv[i]
            opts[name[2:]] = value
        elif token in ("--write-proposals", "--strict"):
            opts[token[2:]] = True
        elif token.startswith("-"):
            raise _UsageError(f"unknown argument: {token}")
        else:
            opts["targets"].append(token)
        i += 1
    if opts["format"] not in ("json", "text"):
        raise _UsageError(f"--format must be json or text, not {opts['format']}")
    if not opts["targets"]:
        raise _UsageError("missing <target>")
    return opts


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(str(exc))

    try:
        report = check(
            opts["targets"],
            Path(opts["repo-root"]),
            opts["model"],
            write_proposals=opts["write-proposals"],
        )
    except ValueError as exc:
        return _usage_error(str(exc))

    if opts["format"] == "json":
        print(json.dumps(report.to_dict()))
    else:
        for finding in report.findings:
            print(f"{finding['criterion_id']}: {finding['kind']}: {finding['message']}")
        for gap in report.gaps:
            print(f"{gap['criterion_id']}: {gap['kind']}: {gap['missing']}")
            print(f"  propose: {gap['proposed_text']} (in {gap['target_file']})")
        print(
            f"{len(report.criteria_checked)} criteria checked, "
            f"{len(report.findings)} findings, {len(report.gaps)} gaps"
        )

    if any(f.get("severity") == "fail" for f in report.lint_findings):
        return 1
    if opts["strict"] and (report.findings or report.gaps):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
