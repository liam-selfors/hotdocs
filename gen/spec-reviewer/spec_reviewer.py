"""Spec Reviewer: checks acceptance criteria against what their test authors see.

Advisory only. Writes nothing except proposals under
``<repo_root>/.hotdocs/proposals/`` when asked.
"""

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

USAGE = (
    "usage: hotdocs spec check <target>... [--model=<model>] [--write-proposals] "
    "[--strict] [--format=json|text] [--repo-root=<dir>]"
)

_STEP_WORDS = ("Given", "When", "Then")
_CHECKED_STEPS = ("When", "Then")
_GAP_KINDS = ("guess", "unstated_behavior")
_CODE_SPAN = re.compile(r"`([^`]*)`")
_UNPARSEABLE = "reply was not the JSON object asked for"
_FINDING_FIELDS = ("rule_id", "severity", "file", "line", "message", "rationale")


@dataclasses.dataclass
class ReviewReport:
    targets: list
    criteria_checked: list
    findings: list
    gaps: list
    writable: dict
    lint_findings: list
    proposals: list
    degraded: bool

    def __getitem__(self, key):
        return self.to_dict()[key]

    def to_dict(self):
        return dataclasses.asdict(self)


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    gen = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen.parent


def _load(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug if repo_root is not None else None
    if base is None or not base.is_dir():
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


def _parse_object(text):
    try:
        return json.loads(text[text.find("{"): text.rfind("}") + 1])
    except ValueError:
        return None


def _make_judge(complete, model, llm_backend):
    def judge(term, local_text, glossary_text):
        prompt = (
            "You judge whether a component's local definition of a term conflicts "
            "with the corpus glossary.\n\n"
            "Term: " + str(term) + "\n\n"
            "Local text:\n" + str(local_text) + "\n\n"
            "Glossary text:\n" + str(glossary_text) + "\n\n"
            "Reply with exactly one JSON object and nothing else:\n"
            '{"conflicts": <bool>, "rationale": "<text>"}\n'
        )
        resp = complete(prompt, model, backend=llm_backend)
        obj = None if _get(resp, "model_call_error") else _parse_object(_get(resp, "text"))
        if (
            obj is not None
            and isinstance(obj.get("conflicts"), bool)
            and isinstance(obj.get("rationale"), str)
        ):
            return (obj["conflicts"], obj["rationale"])
        return None

    return judge


def glossary_judge(model, llm_backend=None):
    endpoint = _load("llm-endpoint", "llm_endpoint", None)
    return _make_judge(endpoint.complete, model, llm_backend)


def _resolve_targets(targets, repo_root):
    components = repo_root / "specs" / "components"
    owners = {}
    slugs = set()
    for target in targets:
        comp_dir = components / target[len("comp-"):]
        if target.startswith("comp-") and comp_dir.is_dir():
            slug = comp_dir.name
            slugs.add(slug)
            for path in (comp_dir / "acceptance").glob("AC-*.md"):
                owners[path.stem] = slug
            continue
        matches = sorted(components.glob(f"*/acceptance/{target}.md"))
        if not matches:
            raise ValueError(f"unknown target id: {target}")
        slug = matches[0].parent.parent.name
        slugs.add(slug)
        owners[target] = slug
    return owners, sorted(slugs)


def _step_tokens(criterion_text):
    tokens = []
    inside = False
    step = None
    for line in criterion_text.splitlines():
        stripped = line.strip()
        if not inside:
            inside = stripped == "```gherkin"
            continue
        if stripped == "```":
            break
        words = line.split()
        if words and words[0] in _STEP_WORDS:
            step = words[0]
        if step in _CHECKED_STEPS:
            for raw in _CODE_SPAN.findall(line):
                token = raw.strip().split("<", 1)[0].strip()
                if token and token not in tokens:
                    tokens.append(token)
    return tokens


def _invisible_findings(criterion_id, bundle):
    visible = "".join(
        [
            _get(bundle, "requirement_text"),
            _get(bundle, "interface"),
            _get(bundle, "glossary"),
        ]
        + list(_get(bundle, "dependency_interfaces").values())
    )
    findings = []
    for token in _step_tokens(_get(bundle, "criterion_text")):
        if token not in visible:
            findings.append(
                {
                    "criterion_id": criterion_id,
                    "kind": "invisible_reference",
                    "token": token,
                    "message": f"`{token}` appears in {criterion_id} but not in what its test author sees",
                }
            )
    return findings


def _criterion_prompt(bundle):
    deps = _get(bundle, "dependency_interfaces")
    dep_text = "\n\n".join(f"### {name}\n{text}" for name, text in deps.items())
    return (
        "You are the author of the executable test for one acceptance criterion. "
        "You see only the material below and cannot ask for more. Decide whether "
        "you could write the test from it, list every fact you would have to "
        "guess (kind \"guess\"), and every behavior the criterion checks that no "
        "requirement or interface text states (kind \"unstated_behavior\"). For "
        "each gap, propose the spec text that would close it and the spec file "
        "it belongs in.\n\n"
        "Reply with exactly one JSON object and nothing else:\n"
        '{"writable": <bool>,\n'
        ' "gaps": [{"kind": "guess" | "unstated_behavior", "missing": "<text>",\n'
        '           "proposed_text": "<text>", "target_file": "<path>"}]}\n\n'
        "## component_id\n" + str(_get(bundle, "component_id")) + "\n\n"
        "## criterion_id\n" + str(_get(bundle, "criterion_id")) + "\n\n"
        "## covers\n" + str(_get(bundle, "covers")) + "\n\n"
        "## criterion_text\n" + str(_get(bundle, "criterion_text")) + "\n\n"
        "## requirement_text\n" + str(_get(bundle, "requirement_text")) + "\n\n"
        "## interface\n" + str(_get(bundle, "interface")) + "\n\n"
        "## glossary\n" + str(_get(bundle, "glossary")) + "\n\n"
        "## dependency_interfaces\n" + dep_text + "\n"
    )


def _write_proposals(repo_root, criteria, gaps):
    written = []
    for criterion_id in criteria:
        own = [gap for gap in gaps if gap["criterion_id"] == criterion_id]
        if not own:
            continue
        lines = [f"# Proposals for {criterion_id}"]
        for gap in own:
            lines += [
                "",
                f"- kind: {gap['kind']}",
                f"  missing: {gap['missing']}",
                f"  target_file: {gap['target_file']}",
                f"  proposed_text: {gap['proposed_text']}",
            ]
        rel = f".hotdocs/proposals/{criterion_id}.md"
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(rel)
    return written


def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):
    repo_root = Path(repo_root)
    owners, slugs = _resolve_targets(targets, repo_root)
    criteria = sorted(owners)

    complete = None
    judge = None
    if model:
        complete = _load("llm-endpoint", "llm_endpoint", repo_root).complete
        judge = _make_judge(complete, model, llm_backend)

    linter = _load("spec-linter", "spec_linter", repo_root)
    paths = [repo_root / "specs" / "components" / slug for slug in slugs]
    lint_report = linter.lint(paths, repo_root, judge=judge)
    lint_findings = [
        {name: _get(f, name) for name in _FINDING_FIELDS}
        for f in _get(lint_report, "findings")
    ]
    if any(f["severity"] == "fail" for f in lint_findings):
        return ReviewReport(
            targets=list(targets),
            criteria_checked=[],
            findings=[],
            gaps=[],
            writable={},
            lint_findings=lint_findings,
            proposals=[],
            degraded=not model,
        )

    assembler = _load("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    findings = []
    gaps = []
    writable = {}
    for criterion_id in criteria:
        bundle = assembler.assemble_criterion("comp-" + owners[criterion_id], criterion_id, repo_root)
        findings.extend(_invisible_findings(criterion_id, bundle))
        writable[criterion_id] = None
        if complete is None:
            continue
        resp = complete(_criterion_prompt(bundle), model, backend=llm_backend)
        error = _get(resp, "model_call_error")
        obj = None if error else _parse_object(_get(resp, "text"))
        if obj is None or not isinstance(obj.get("writable"), bool):
            message = (_get(error, "message") or str(error)) if error else _UNPARSEABLE
            findings.append(
                {
                    "criterion_id": criterion_id,
                    "kind": "model_unparseable",
                    "token": "",
                    "message": message,
                }
            )
            continue
        writable[criterion_id] = obj["writable"]
        for gap in obj.get("gaps", []):
            if gap.get("kind") in _GAP_KINDS:
                gaps.append(
                    {
                        "criterion_id": criterion_id,
                        "kind": gap.get("kind"),
                        "missing": gap.get("missing"),
                        "proposed_text": gap.get("proposed_text"),
                        "target_file": gap.get("target_file"),
                    }
                )

    proposals = []
    if write_proposals and gaps:
        proposals = _write_proposals(repo_root, criteria, gaps)

    return ReviewReport(
        targets=list(targets),
        criteria_checked=criteria,
        findings=findings,
        gaps=gaps,
        writable=writable,
        lint_findings=lint_findings,
        proposals=proposals,
        degraded=not model,
    )


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    values = {"--model": None, "--format": "text", "--repo-root": None}
    flags = set()
    targets = []
    i = 0
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in values:
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(f"{name} needs a value")
                i += 1
                value = argv[i]
            values[name] = value
        elif token in ("--write-proposals", "--strict"):
            flags.add(token)
        elif token.startswith("-"):
            return _usage_error(f"unknown argument: {token}")
        else:
            targets.append(token)
        i += 1

    if values["--format"] not in ("json", "text"):
        return _usage_error(f"--format must be json or text, not {values['--format']}")
    if not targets:
        return _usage_error("missing <target>")

    repo_root = Path(values["--repo-root"]) if values["--repo-root"] is not None else Path.cwd()
    try:
        report = check(
            targets,
            repo_root,
            values["--model"],
            write_proposals="--write-proposals" in flags,
        )
    except ValueError as exc:
        return _usage_error(str(exc))

    if values["--format"] == "json":
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

    if any(f["severity"] == "fail" for f in report.lint_findings):
        return 1
    if "--strict" in flags and (report.findings or report.gaps):
        return 1
    return 0
