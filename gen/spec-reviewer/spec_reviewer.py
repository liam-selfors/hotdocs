"""Spec Reviewer: checks each acceptance criterion against what its test
author will see, and (with a model) asks what that author would have to
guess. Advisory only."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

USAGE = ("usage: hotdocs spec check <target>... [--model=<model>] "
         "[--write-proposals] [--strict] [--format=json|text] "
         "[--repo-root=<dir>]")

_GAP_KINDS = ("guess", "unstated_behavior")
_UNPARSEABLE = "reply was not the JSON object asked for"
_CODE_SPAN = re.compile(r"`([^`]*)`")


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
        if key not in {f.name for f in dataclasses.fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------- helpers

def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _finding_dict(f) -> dict:
    if isinstance(f, dict):
        return dict(f)
    return {fl.name: getattr(f, fl.name) for fl in dataclasses.fields(f)}


def _tool_root():
    for d in Path(__file__).resolve().parents:
        if d.name == "gen":
            return d.parent


def _load(slug: str, module: str, repo_root: Path):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module}.py"
    search = None
    if not path.is_file():
        path = base / module / "__init__.py"
        search = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(
        module, path, submodule_search_locations=search)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse_object(text):
    if not isinstance(text, str):
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


# ----------------------------------------------------------- glossary judge

def _make_judge(complete, model, llm_backend):
    def judge(term, local_text, glossary_text):
        prompt = (
            "You judge whether a component's local definition of a term "
            "conflicts with the corpus glossary.\n\n"
            f"Term: {term}\n\n"
            f"Local text:\n{local_text}\n\n"
            f"Glossary text:\n{glossary_text}\n\n"
            "Reply with exactly one JSON object: "
            '{"conflicts": <bool>, "rationale": "<text>"}'
        )
        reply = complete(prompt, model, backend=llm_backend)
        if _get(reply, "model_call_error"):
            return None
        obj = _parse_object(_get(reply, "text"))
        if obj is None:
            return None
        conflicts = obj.get("conflicts")
        rationale = obj.get("rationale")
        if not isinstance(conflicts, bool) or not isinstance(rationale, str):
            return None
        return (conflicts, rationale)
    return judge


def glossary_judge(model: str, llm_backend=None):
    state = {}

    def complete(prompt, model, *, backend=None):
        if "complete" not in state:
            state["complete"] = _get(
                _load("llm-endpoint", "llm_endpoint", _tool_root()), "complete")
        return state["complete"](prompt, model, backend=backend)

    return _make_judge(complete, model, llm_backend)


# ------------------------------------------------------ deterministic check

def _step_tokens(criterion_text: str) -> list:
    tokens = []
    in_block = False
    step = None
    for line in criterion_text.splitlines():
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
        for m in _CODE_SPAN.finditer(line):
            token = m.group(1).strip()
            if "<" in token:
                token = token[:token.index("<")]
            if token and token not in tokens:
                tokens.append(token)
    return tokens


def _criterion_prompt(bundle) -> str:
    deps = _get(bundle, "dependency_interfaces")
    dep_text = "\n\n".join(
        f"### {name}\n{text}" for name, text in deps.items())
    cid = _get(bundle, "criterion_id")
    return (
        f"You are the author of the executable test for acceptance "
        f"criterion {cid}. Below is everything you will see when you write "
        "that test, and nothing else.\n\n"
        f"## component_id\n{_get(bundle, 'component_id')}\n\n"
        f"## criterion_id\n{cid}\n\n"
        f"## covers\n{_get(bundle, 'covers')}\n\n"
        f"## criterion_text\n{_get(bundle, 'criterion_text')}\n\n"
        f"## requirement_text\n{_get(bundle, 'requirement_text')}\n\n"
        f"## interface\n{_get(bundle, 'interface')}\n\n"
        f"## glossary\n{_get(bundle, 'glossary')}\n\n"
        f"## dependency_interfaces\n{dep_text}\n\n"
        f"## testing\n{_get(bundle, 'testing')}\n\n"
        "As this test's author: could you write the test from only the "
        "text above? List each fact you would have to guess (kind "
        '"guess") and each behavior the criterion checks that no '
        'requirement or interface text states (kind "unstated_behavior"), '
        "with the spec text that would close the gap and the spec file it "
        "belongs in. Reply with exactly one JSON object:\n"
        '{"writable": <bool>,\n'
        ' "gaps": [{"kind": "guess" | "unstated_behavior", '
        '"missing": "<text>",\n'
        '           "proposed_text": "<text>", "target_file": "<path>"}]}'
    )


# ------------------------------------------------------------------- check

def check(targets: list, repo_root: Path, model: str | None = None, *,
          llm_backend=None, write_proposals: bool = False) -> ReviewReport:
    repo_root = Path(repo_root)
    comps = repo_root / "specs" / "components"
    criteria = {}
    slugs = set()
    for target in targets:
        if target.startswith("comp-") and (comps / target[5:]).is_dir():
            slug = target[5:]
            slugs.add(slug)
            for f in sorted((comps / slug / "acceptance").glob("AC-*.md")):
                criteria[f.stem] = slug
            continue
        hits = sorted(comps.glob(f"*/acceptance/{target}.md"))
        if not hits:
            raise ValueError(f"unknown target id: {target}")
        slug = hits[0].parent.parent.name
        slugs.add(slug)
        criteria[target] = slug

    degraded = not model
    linter = _load("spec-linter", "spec_linter", repo_root)
    assembler = _load("spec-bundle-assembler", "spec_bundle_assembler",
                      repo_root)
    complete = None
    judge = None
    if model:
        complete = _get(_load("llm-endpoint", "llm_endpoint", repo_root),
                        "complete")
        judge = _make_judge(complete, model, llm_backend)

    paths = [comps / s for s in sorted(slugs)]
    lint_report = _get(linter, "lint")(paths, repo_root, judge=judge)
    lint_findings = [_finding_dict(f) for f in _get(lint_report, "findings")]
    if any(f.get("severity") == "fail" for f in lint_findings):
        return ReviewReport(list(targets), [], [], [], {}, lint_findings,
                            [], degraded)

    assemble_criterion = _get(assembler, "assemble_criterion")
    criteria_checked = sorted(criteria)
    findings = []
    gaps = []
    writable = {}
    for cid in criteria_checked:
        bundle = assemble_criterion(f"comp-{criteria[cid]}", cid, repo_root)
        visible = "".join(
            [_get(bundle, "requirement_text"), _get(bundle, "interface"),
             _get(bundle, "glossary")]
            + list(_get(bundle, "dependency_interfaces").values()))
        for token in _step_tokens(_get(bundle, "criterion_text")):
            if token not in visible:
                findings.append({
                    "criterion_id": cid, "kind": "invisible_reference",
                    "token": token,
                    "message": (f"`{token}` appears in {cid} but not in "
                                "what its test author sees"),
                })
        writable[cid] = None
        if not model:
            continue
        reply = complete(_criterion_prompt(bundle), model,
                         backend=llm_backend)
        error = _get(reply, "model_call_error")
        obj = None if error else _parse_object(_get(reply, "text"))
        if obj is None or not isinstance(obj.get("writable"), bool):
            findings.append({
                "criterion_id": cid, "kind": "model_unparseable",
                "token": "",
                "message": _get(error, "message") if error else _UNPARSEABLE,
            })
            continue
        writable[cid] = obj["writable"]
        for gap in obj.get("gaps", []):
            if isinstance(gap, dict) and gap.get("kind") in _GAP_KINDS:
                gaps.append({
                    "criterion_id": cid, "kind": gap.get("kind"),
                    "missing": gap.get("missing"),
                    "proposed_text": gap.get("proposed_text"),
                    "target_file": gap.get("target_file"),
                })

    proposals = []
    if write_proposals and gaps:
        out_dir = repo_root / ".hotdocs" / "proposals"
        out_dir.mkdir(parents=True, exist_ok=True)
        for cid in criteria_checked:
            mine = [g for g in gaps if g["criterion_id"] == cid]
            if not mine:
                continue
            lines = [f"# Proposals for {cid}"]
            for g in mine:
                lines += ["", f"- kind: {g['kind']}",
                          f"  missing: {g['missing']}",
                          f"  target_file: {g['target_file']}",
                          f"  proposed_text: {g['proposed_text']}"]
            (out_dir / f"{cid}.md").write_text("\n".join(lines) + "\n",
                                               encoding="utf-8")
            proposals.append(f".hotdocs/proposals/{cid}.md")

    return ReviewReport(list(targets), criteria_checked, findings, gaps,
                        writable, lint_findings, proposals, degraded)


# -------------------------------------------------------------------- CLI

def _usage(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    value_flags = ("--model", "--format", "--repo-root")
    bool_flags = ("--write-proposals", "--strict")
    opts = {"--format": "text", "--model": None, "--repo-root": None,
            "--write-proposals": False, "--strict": False}
    targets = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-"):
            name, eq, val = tok.partition("=")
            if name in value_flags:
                if not eq:
                    if i + 1 >= len(argv):
                        return _usage(f"{name} needs a value")
                    i += 1
                    val = argv[i]
                opts[name] = val
            elif name in bool_flags and not eq:
                opts[name] = True
            else:
                return _usage(f"unknown argument: {tok}")
        else:
            targets.append(tok)
        i += 1

    if opts["--format"] not in ("json", "text"):
        return _usage(f"--format must be json or text, not "
                      f"{opts['--format']}")
    if not targets:
        return _usage("at least one <target> is required")

    repo_root = Path(opts["--repo-root"]) if opts["--repo-root"] else Path.cwd()
    try:
        report = check(targets, repo_root, opts["--model"],
                       write_proposals=opts["--write-proposals"])
    except ValueError as exc:
        return _usage(str(exc))

    if opts["--format"] == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for f in report.findings:
            print(f"{f['criterion_id']}: {f['kind']}: {f['message']}")
        for g in report.gaps:
            print(f"{g['criterion_id']}: {g['kind']}: {g['missing']}")
            print(f"  propose: {g['proposed_text']} (in {g['target_file']})")
        print(f"{len(report.criteria_checked)} criteria checked, "
              f"{len(report.findings)} findings, {len(report.gaps)} gaps")

    if any(f.get("severity") == "fail" for f in report.lint_findings):
        return 1
    if opts["--strict"] and (report.findings or report.gaps):
        return 1
    return 0
