"""Spec Reviewer: checks whether each acceptance criterion can be written
from what its test author sees, and proposes spec text closing each gap.

Advisory only: never changes a file under ``specs/``.
"""

import dataclasses
import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

USAGE = (
    "usage: hotdocs spec check <target>... [--model=<model>] [--write-proposals] "
    "[--strict] [--format=json|text] [--repo-root=<dir>]"
)

_GAP_KINDS = ("guess", "unstated_behavior")
_STEP_WORDS = ("Given", "When", "Then")
_CODE_SPAN = re.compile(r"`([^`]*)`")
_UNPARSEABLE = "reply was not the JSON object asked for"
_BUNDLE_FIELDS = (
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
    "testing",
)
_REPLY_SHAPE = (
    '{"writable": <bool>,\n'
    ' "gaps": [{"kind": "guess" | "unstated_behavior", "missing": "<text>",\n'
    '           "proposed_text": "<text>", "target_file": "<path>"}]}'
)
_JUDGE_SHAPE = '{"conflicts": <bool>, "rationale": "<text>"}'


@dataclasses.dataclass
class ReviewReport(Mapping):
    targets: list
    criteria_checked: list
    findings: list
    gaps: list
    writable: dict
    lint_findings: list
    proposals: list
    degraded: bool

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def to_dict(self):
        return dataclasses.asdict(self)


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    here = Path(__file__).resolve().parent
    return next(p.parent for p in [here, *here.parents] if p.name == "gen")


def _load(slug, module, repo_root):
    directory = None
    if repo_root is not None:
        directory = Path(repo_root) / "gen" / slug
    if directory is None or not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module}.py"
    spec = importlib.util.spec_from_file_location(module, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse_object(text):
    text = text or ""
    try:
        obj = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _make_judge(model, llm_backend, complete):
    def judge(term, local_text, glossary_text):
        prompt = (
            "Decide whether a component's local definition of a term conflicts "
            "with the glossary's definition of it.\n\n"
            f"Term: {term}\n\n"
            f"Local definition:\n{local_text}\n\n"
            f"Glossary:\n{glossary_text}\n\n"
            f"Reply with one JSON object: {_JUDGE_SHAPE}\n"
        )
        reply = complete(prompt, model, backend=llm_backend)
        if _get(reply, "model_call_error"):
            return None
        obj = _parse_object(_get(reply, "text"))
        if (
            obj is not None
            and isinstance(obj.get("conflicts"), bool)
            and isinstance(obj.get("rationale"), str)
        ):
            return (obj["conflicts"], obj["rationale"])
        return None

    return judge


def glossary_judge(model, llm_backend=None):
    def complete(prompt, model_, *, backend=None):
        return _load("llm-endpoint", "llm_endpoint", None).complete(
            prompt, model_, backend=backend
        )

    return _make_judge(model, llm_backend, complete)


def _resolve_targets(targets, repo_root):
    comps = repo_root / "specs" / "components"
    criteria = {}
    slugs = []
    for target in targets:
        if target.startswith("comp-") and (comps / target[5:]).is_dir():
            slug = target[5:]
            for path in sorted((comps / slug / "acceptance").glob("AC-*.md")):
                criteria[path.stem] = slug
        else:
            hits = sorted(comps.glob(f"*/acceptance/{target}.md"))
            if not hits:
                raise ValueError(f"unknown target: {target}")
            slug = hits[0].parent.parent.name
            criteria[target] = slug
        if slug not in slugs:
            slugs.append(slug)
    return criteria, sorted(slugs)


def _step_tokens(criterion_text):
    tokens = []
    in_block = False
    step = None
    for line in criterion_text.splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```gherkin"):
                in_block = True
                step = None
            continue
        if stripped.startswith("```"):
            in_block = False
            continue
        if not stripped:
            continue
        first = stripped.split()[0]
        if first in _STEP_WORDS:
            step = first
        elif not (first in ("And", "But") or line[0].isspace()):
            step = None
        if step in ("When", "Then"):
            for raw in _CODE_SPAN.findall(line):
                token = raw.strip()
                if "<" in token:
                    token = token.split("<", 1)[0]
                if token and token not in tokens:
                    tokens.append(token)
    return tokens


def _criterion_prompt(bundle):
    parts = [
        f"You are the author of the acceptance test for criterion "
        f"{_get(bundle, 'criterion_id')}. You see only the material below and "
        "cannot ask for more. Say whether you could write that test from it, "
        "what you would have to guess, and what behavior the criterion checks "
        "that no requirement or interface text states. For each gap propose "
        "the spec text that would close it and the spec file it belongs in.",
        f"Reply with one JSON object:\n{_REPLY_SHAPE}",
    ]
    for name in _BUNDLE_FIELDS:
        value = _get(bundle, name)
        if name == "dependency_interfaces":
            value = "\n\n".join(
                f"### {dep}\n{text}" for dep, text in (value or {}).items()
            )
        parts.append(f"## {name}\n{value or ''}")
    return "\n\n".join(parts) + "\n"


def _finding_dict(finding):
    return {
        name: _get(finding, name)
        for name in ("rule_id", "severity", "file", "line", "message", "rationale")
    }


def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):
    repo_root = Path(repo_root)
    criteria, slugs = _resolve_targets(targets, repo_root)

    linter = _load("spec-linter", "spec_linter", repo_root)
    complete = None
    judge = None
    if model:
        complete = _load("llm-endpoint", "llm_endpoint", repo_root).complete
        judge = _make_judge(model, llm_backend, complete)
    paths = [repo_root / "specs" / "components" / slug for slug in slugs]
    lint_report = linter.lint(paths, repo_root, judge=judge)
    lint_findings = [_finding_dict(f) for f in (_get(lint_report, "findings") or [])]
    degraded = not model

    if any(f["severity"] == "fail" for f in lint_findings):
        return ReviewReport(
            list(targets), [], [], [], {}, lint_findings, [], degraded
        )

    assembler = _load("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    checked = sorted(criteria)
    findings = []
    gaps = []
    writable = {}
    for cid in checked:
        bundle = assembler.assemble_criterion(f"comp-{criteria[cid]}", cid, repo_root)
        visible = (
            (_get(bundle, "requirement_text") or "")
            + (_get(bundle, "interface") or "")
            + (_get(bundle, "glossary") or "")
            + "".join((_get(bundle, "dependency_interfaces") or {}).values())
        )
        for token in _step_tokens(_get(bundle, "criterion_text") or ""):
            if token not in visible:
                findings.append({
                    "criterion_id": cid,
                    "kind": "invisible_reference",
                    "token": token,
                    "message": f"`{token}` appears in {cid} but not in what "
                               "its test author sees",
                })
        writable[cid] = None
        if not model:
            continue
        reply = complete(_criterion_prompt(bundle), model, backend=llm_backend)
        error = _get(reply, "model_call_error")
        obj = None if error else _parse_object(_get(reply, "text"))
        if obj is None or not isinstance(obj.get("writable"), bool):
            findings.append({
                "criterion_id": cid,
                "kind": "model_unparseable",
                "token": "",
                "message": _get(error, "message") if error else _UNPARSEABLE,
            })
            continue
        writable[cid] = obj["writable"]
        for gap in obj.get("gaps") or []:
            if isinstance(gap, dict) and gap.get("kind") in _GAP_KINDS:
                gaps.append({
                    "criterion_id": cid,
                    "kind": gap["kind"],
                    "missing": gap.get("missing"),
                    "proposed_text": gap.get("proposed_text"),
                    "target_file": gap.get("target_file"),
                })

    proposals = []
    if write_proposals and gaps:
        out_dir = repo_root / ".hotdocs" / "proposals"
        out_dir.mkdir(parents=True, exist_ok=True)
        for cid in checked:
            own = [g for g in gaps if g["criterion_id"] == cid]
            if not own:
                continue
            lines = [f"# Proposals for {cid}"]
            for gap in own:
                lines += [
                    "",
                    f"- kind: {gap['kind']}",
                    f"  missing: {gap['missing']}",
                    f"  target_file: {gap['target_file']}",
                    f"  proposed_text: {gap['proposed_text']}",
                ]
            (out_dir / f"{cid}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
            proposals.append(f".hotdocs/proposals/{cid}.md")

    return ReviewReport(
        list(targets), checked, findings, gaps, writable, lint_findings,
        proposals, degraded,
    )


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    targets = []
    opts = {}
    flags = set()
    i = 0
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in ("--model", "--format", "--repo-root"):
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(f"{name} needs a value")
                i += 1
                value = argv[i]
            opts[name] = value
        elif token in ("--write-proposals", "--strict"):
            flags.add(token)
        elif token.startswith("-"):
            return _usage_error(f"unknown argument: {token}")
        else:
            targets.append(token)
        i += 1

    fmt = opts.get("--format", "text")
    if fmt not in ("json", "text"):
        return _usage_error(f"--format must be json or text, not {fmt}")
    if not targets:
        return _usage_error("missing <target>")

    repo_root = Path(opts["--repo-root"]) if "--repo-root" in opts else Path.cwd()
    try:
        report = check(
            targets,
            repo_root,
            opts.get("--model"),
            write_proposals="--write-proposals" in flags,
        )
    except ValueError as exc:
        return _usage_error(str(exc))

    if fmt == "json":
        print(json.dumps(report.to_dict(), indent=2))
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

    if any(f["severity"] == "fail" for f in report.lint_findings):
        return 1
    if "--strict" in flags and (report.findings or report.gaps):
        return 1
    return 0
