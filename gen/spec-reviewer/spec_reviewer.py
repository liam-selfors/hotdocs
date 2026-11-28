"""Spec Reviewer: checks each acceptance criterion against what its test author sees."""

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

SCOPE_SENTENCE = (
    "The pipeline fixes the test framework (pytest), the test file's name and "
    "location, and how the test reaches the component's code: never report any "
    "of these as a gap."
)

GAP_KINDS = ("guess", "unstated_behavior")
UNPARSEABLE_MESSAGE = "reply was not the JSON object asked for"
FINDING_FIELDS = ("rule_id", "severity", "file", "line", "message", "rationale")
BUNDLE_FIELDS = (
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

_SPAN_RE = re.compile(r"`([^`]*)`")


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

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def __contains__(self, key):
        return key in self.keys()

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------- helpers


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load(repo_root: Path, slug: str, module: str):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    spec = importlib.util.spec_from_file_location(module, base / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _json_object(text):
    text = text or ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _error_message(err) -> str:
    return f"{_get(err, 'category')}: {_get(err, 'message')}"


# ---------------------------------------------------------------- judge


def _make_judge(complete, model, llm_backend):
    def judge(term, local_text, glossary_text):
        prompt = (
            "You judge whether a component's local definition of a glossary term "
            "conflicts with the canonical glossary.\n\n"
            f"Term: {term}\n\n"
            f"Local definition:\n{local_text}\n\n"
            f"Glossary:\n{glossary_text}\n\n"
            'Reply with one JSON object: {"conflicts": <bool>, "rationale": "<text>"}'
        )
        response = complete(prompt, model, backend=llm_backend)
        if _get(response, "model_call_error"):
            return None
        obj = _json_object(_get(response, "text"))
        if obj is None:
            return None
        conflicts = obj.get("conflicts")
        rationale = obj.get("rationale")
        if not isinstance(conflicts, bool) or not isinstance(rationale, str):
            return None
        return (conflicts, rationale)

    return judge


def glossary_judge(model: str, llm_backend=None):
    llm_endpoint = _load(_tool_root(), "llm-endpoint", "llm_endpoint")
    return _make_judge(llm_endpoint.complete, model, llm_backend)


# ---------------------------------------------------------------- checks


def _resolve_targets(targets, repo_root: Path):
    comps_dir = repo_root / "specs" / "components"
    criteria = {}
    slugs = set()
    for target in targets:
        if target.startswith("comp-") and (comps_dir / target[5:]).is_dir():
            slug = target[5:]
            slugs.add(slug)
            for path in (comps_dir / slug / "acceptance").glob("AC-*.md"):
                criteria[path.stem] = slug
        else:
            hits = sorted(comps_dir.glob(f"*/acceptance/{target}.md"))
            if not hits:
                raise ValueError(f"unknown target id: {target}")
            slug = hits[0].parent.parent.name
            slugs.add(slug)
            criteria[target] = slug
    return criteria, sorted(slugs)


def _assets(component_md: Path):
    if not component_md.exists():
        return []
    lines = component_md.read_text(encoding="utf-8").splitlines()
    marks = [i for i, line in enumerate(lines) if line.strip() == "---"][:2]
    if len(marks) < 2:
        return []
    line = next(
        (l for l in lines[marks[0] + 1 : marks[1]] if l.startswith("assets:")), None
    )
    if line is None or "[" not in line:
        return []
    inner = line[line.index("[") + 1 :].split("]")[0]
    assets = []
    for item in inner.split(","):
        item = item.strip()
        if ":" not in item:
            continue
        kind, path = item.split(":", 1)
        assets.append((kind.strip(), path.strip()))
    return assets


def _asset_findings(slugs, repo_root: Path):
    findings = []
    for slug in slugs:
        comp_dir = repo_root / "specs" / "components" / slug
        for _kind, path in _assets(comp_dir / "component.md"):
            name = path.rsplit("/", 1)[-1]
            rel = f"specs/components/{slug}/interface/assets/{name}.md"
            if not (repo_root / rel).exists():
                findings.append(
                    {
                        "criterion_id": f"comp-{slug}",
                        "kind": "asset_interface_missing",
                        "token": path,
                        "message": f"`{path}` has no interface file {rel}",
                    }
                )
    return findings


def _step_tokens(criterion_text: str):
    tokens = []
    in_block = False
    step = None
    for line in (criterion_text or "").splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped == "```gherkin":
                in_block = True
                step = None
            continue
        if stripped == "```":
            in_block = False
            continue
        words = stripped.split()
        if words and words[0] in ("Given", "When", "Then"):
            step = words[0]
        if step not in ("When", "Then"):
            continue
        for span in _SPAN_RE.findall(line):
            token = span.strip().split("<", 1)[0]
            if token and token not in tokens:
                tokens.append(token)
    return tokens


def _criterion_prompt(bundle) -> str:
    parts = [
        "You are the author of the pytest test for one acceptance criterion. "
        "Below is everything you will see when you write that test. Report every "
        "fact you would have to guess, and every behavior the criterion checks "
        "that no requirement or interface text states.",
        SCOPE_SENTENCE,
    ]
    for name in BUNDLE_FIELDS:
        value = _get(bundle, name, "")
        if isinstance(value, dict):
            value = "\n\n".join(f"### {k}\n{v}" for k, v in value.items())
        parts.append(f"## {name}\n{value}")
    parts.append(
        "Reply with one JSON object:\n"
        '{"writable": <bool>,\n'
        ' "gaps": [{"kind": "guess" | "unstated_behavior", "missing": "<text>",\n'
        '           "proposed_text": "<text>", "target_file": "<path>"}]}'
    )
    return "\n\n".join(parts)


def _write_proposals(gaps, criteria, repo_root: Path):
    written = []
    for cid in criteria:
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
        rel = f".hotdocs/proposals/{cid}.md"
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(rel)
    return written


def check(
    targets: list,
    repo_root: Path,
    model: str | None = None,
    *,
    llm_backend=None,
    write_proposals: bool = False,
) -> ReviewReport:
    repo_root = Path(repo_root)
    criteria_map, slugs = _resolve_targets(targets, repo_root)
    criteria = sorted(criteria_map)
    report = ReviewReport(targets=list(targets), degraded=model is None)

    report.findings = _asset_findings(slugs, repo_root)

    complete = None
    judge = None
    if model:
        complete = _load(repo_root, "llm-endpoint", "llm_endpoint").complete
        judge = _make_judge(complete, model, llm_backend)

    spec_linter = _load(repo_root, "spec-linter", "spec_linter")
    paths = [repo_root / "specs" / "components" / slug for slug in slugs]
    lint_report = spec_linter.lint(paths, repo_root, judge=judge)
    report.lint_findings = [
        {name: _get(f, name) for name in FINDING_FIELDS}
        for f in _get(lint_report, "findings")
    ]
    if any(f["severity"] == "fail" for f in report.lint_findings):
        return report

    assembler = _load(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
    report.criteria_checked = criteria
    for cid in criteria:
        bundle = assembler.assemble_criterion(f"comp-{criteria_map[cid]}", cid, repo_root)
        visible = "".join(
            [
                _get(bundle, "requirement_text", ""),
                _get(bundle, "interface", ""),
                _get(bundle, "glossary", ""),
                *_get(bundle, "dependency_interfaces", {}).values(),
            ]
        )
        for token in _step_tokens(_get(bundle, "criterion_text", "")):
            if token not in visible:
                report.findings.append(
                    {
                        "criterion_id": cid,
                        "kind": "invisible_reference",
                        "token": token,
                        "message": f"`{token}` appears in {cid} but not in what its test author sees",
                    }
                )

        report.writable[cid] = None
        if not model:
            continue
        response = complete(_criterion_prompt(bundle), model, backend=llm_backend)
        error = _get(response, "model_call_error")
        obj = None if error else _json_object(_get(response, "text"))
        if obj is None or not isinstance(obj.get("writable"), bool):
            report.findings.append(
                {
                    "criterion_id": cid,
                    "kind": "model_unparseable",
                    "token": "",
                    "message": _error_message(error) if error else UNPARSEABLE_MESSAGE,
                }
            )
            continue
        report.writable[cid] = obj["writable"]
        for gap in obj.get("gaps", []):
            if gap.get("kind") not in GAP_KINDS:
                continue
            report.gaps.append(
                {
                    "criterion_id": cid,
                    "kind": gap["kind"],
                    "missing": gap.get("missing", ""),
                    "proposed_text": gap.get("proposed_text", ""),
                    "target_file": gap.get("target_file", ""),
                }
            )

    if write_proposals and report.gaps:
        report.proposals = _write_proposals(report.gaps, criteria, repo_root)
    return report


# ---------------------------------------------------------------- CLI


class _UsageError(Exception):
    pass


def _parse(argv):
    opts = {
        "targets": [],
        "model": None,
        "write_proposals": False,
        "strict": False,
        "format": "text",
        "repo_root": ".",
    }
    value_flags = {"--model": "model", "--format": "format", "--repo-root": "repo_root"}
    i = 0
    while i < len(argv):
        token = argv[i]
        i += 1
        if token == "--write-proposals":
            opts["write_proposals"] = True
        elif token == "--strict":
            opts["strict"] = True
        elif token.split("=", 1)[0] in value_flags:
            name, has_eq, value = token.partition("=")
            if not has_eq:
                if i >= len(argv):
                    raise _UsageError(f"{name} requires a value")
                value = argv[i]
                i += 1
            opts[value_flags[name]] = value
        elif token.startswith("-"):
            raise _UsageError(f"unknown argument: {token}")
        else:
            opts["targets"].append(token)
    if opts["format"] not in ("json", "text"):
        raise _UsageError(f"--format must be json or text, not {opts['format']}")
    if not opts["targets"]:
        raise _UsageError("at least one <target> is required")
    return opts


def _usage_error(cause) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        opts = _parse(list(argv))
        report = check(
            opts["targets"],
            Path(opts["repo_root"]),
            opts["model"],
            write_proposals=opts["write_proposals"],
        )
    except _UsageError as exc:
        return _usage_error(exc)
    except ValueError as exc:
        return _usage_error(exc)

    if opts["format"] == "json":
        print(json.dumps(report.to_dict()))
    else:
        for f in report.findings:
            print(f"{f['criterion_id']}: {f['kind']}: {f['message']}")
        for g in report.gaps:
            print(f"{g['criterion_id']}: {g['kind']}: {g['missing']}")
            print(f"  propose: {g['proposed_text']} (in {g['target_file']})")
        print(
            f"{len(report.criteria_checked)} criteria checked, "
            f"{len(report.findings)} findings, {len(report.gaps)} gaps"
        )

    if any(f["severity"] == "fail" for f in report.lint_findings):
        return 1
    if opts["strict"] and (report.findings or report.gaps):
        return 1
    return 0
