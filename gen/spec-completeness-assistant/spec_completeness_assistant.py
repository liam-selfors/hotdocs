"""Spec Completeness Assistant (comp-spec-completeness-assistant).

Advisory only (R-ASSIST-006): nothing here can block a merge. The report is
returned to the caller and never fed into any gate.

R-ASSIST-008: every suggestion in a ``CompletenessReport`` is addressable by
a stable id (a lint finding's ``rule_id``, a component id in
``predicted_blast_radius``/``hint_previews``, a redundancy flag's
``new_requirement``/``overlaps_with`` R-ids), which is the hook a UI/tooling
layer uses to record a developer's accepted/overridden response. Capturing
and storing that response is out of scope here.
"""

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

_REDUNDANCY_KEYS = ("new_requirement", "overlaps_with", "rationale")
_FLAGS = ("--changed", "--repo-root", "--format", "--model")
_FENCE = re.compile(r"^```[^\n]*\n(.*?)\n?```$", re.DOTALL)


@dataclasses.dataclass
class CompletenessReport:
    lint_findings: list
    predicted_blast_radius: list
    hint_previews: dict
    completeness_score: float | None
    completeness_rationale: str | None
    redundancy_flags: list
    degraded: bool

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    gen = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen.parent


def _load(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _render_findings(findings):
    return "\n".join(
        f"- [{_get(f, 'severity')}] {_get(f, 'rule_id')} "
        f"{_get(f, 'file')}:{_get(f, 'line')}: {_get(f, 'message')}"
        for f in findings
    )


def _render_bundles(bundles):
    parts = []
    for cid, bundle in bundles.items():
        parts.append(
            f"### {cid}\n\n#### SPEC\n{_get(bundle, 'spec')}\n\n"
            f"#### INTERFACE\n{_get(bundle, 'interface')}\n\n"
            f"#### DEPENDENCY INTERFACES\n"
            f"{json.dumps(_get(bundle, 'dependency_interfaces'), indent=2)}\n\n"
            f"#### GLOSSARY\n{_get(bundle, 'glossary')}"
        )
    return "\n\n".join(parts)


def _completeness_prompt(changed_ids, findings, radius, bundles):
    return (
        "You are assessing whether a draft spec change is complete.\n"
        f"Changed spec ids: {', '.join(changed_ids)}\n"
        f"Predicted blast radius: {', '.join(radius)}\n\n"
        "spec-linter findings (including any R-LINT-011/R-LINT-015 glossary "
        "findings; surface them, do not re-detect them):\n"
        f"{_render_findings(findings)}\n\n"
        "Judge: whether touched requirements have present, non-trivial "
        "acceptance criteria; whether a dependent's interface/ content looks "
        "like it needs a matching update that was not made; whether the "
        "change's Definitions entries conflict with the glossary.\n\n"
        "Impacted components' hint-mode spec bundles:\n\n"
        f"{_render_bundles(bundles)}\n\n"
        "Reply with only a JSON object of exactly this shape:\n"
        '{"completeness_score": <number 0.0-1.0>, '
        '"completeness_rationale": "<structured rationale>"}\n'
    )


def _redundancy_prompt(changed_ids, bundles):
    return (
        "You are checking a draft spec change for redundancy: does any changed "
        "requirement restate behavior already specified elsewhere in the "
        "corpus, even if worded differently?\n"
        f"Changed requirement ids: {', '.join(changed_ids)}\n\n"
        "Corpus context (impacted components' hint-mode spec bundles):\n\n"
        f"{_render_bundles(bundles)}\n\n"
        "Reply with only a JSON object of exactly this shape, listing only "
        "real overlaps (an empty list when there are none):\n"
        '{"redundancy_flags": [{"new_requirement": "<changed R-id>", '
        '"overlaps_with": "<pre-existing R-id>", "rationale": "<why>"}]}\n'
    )


def _complete_json(llm, prompt, model, llm_backend):
    response = llm.complete(prompt, model, backend=llm_backend)
    if _get(response, "model_call_error"):
        return None
    text = _get(response, "text").strip()
    match = _FENCE.match(text)
    if match:
        text = match.group(1)
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _nonempty_str(value):
    return isinstance(value, str) and bool(value.strip())


def assist(changed_ids, repo_root, model=None, *, llm_backend=None):
    repo_root = Path(repo_root)
    degraded = model is None

    spec_linter = _load("spec-linter", "spec_linter", repo_root)
    lint_report = spec_linter.lint(None, repo_root)
    findings = list(_get(lint_report, "findings"))
    if any(_get(f, "severity") == "fail" for f in findings):
        return CompletenessReport(findings, [], {}, None, None, [], degraded)

    impact_analyzer = _load("impact-analyzer", "impact_analyzer", repo_root)
    blast = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
    radius = [_get(entry, "component_id") for entry in _get(blast, "impacted")]

    assembler = _load("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    generator = None if degraded else _load("generator", "generator", repo_root)
    bundles = {}
    previews = {}
    for cid in radius:
        bundle = assembler.assemble(cid, repo_root=repo_root, mode="hint")
        bundles[cid] = bundle
        previews[cid] = bundle
        if generator is not None:
            previews[cid] = generator.generate(
                bundle, model, None, repo_root=repo_root, llm_backend=llm_backend
            )

    score = None
    rationale = None
    flags = []
    if not degraded:
        llm = _load("llm-endpoint", "llm_endpoint", repo_root)

        data = _complete_json(
            llm, _completeness_prompt(changed_ids, findings, radius, bundles),
            model, llm_backend,
        )
        if data is not None:
            raw_score = data.get("completeness_score")
            raw_rationale = data.get("completeness_rationale")
            if _is_number(raw_score) and _nonempty_str(raw_rationale):
                score = min(1.0, max(0.0, float(raw_score)))
                rationale = raw_rationale

        data = _complete_json(
            llm, _redundancy_prompt(changed_ids, bundles), model, llm_backend
        )
        raw_flags = data.get("redundancy_flags") if data is not None else None
        if isinstance(raw_flags, list):
            flags = [
                {k: entry[k] for k in _REDUNDANCY_KEYS}
                for entry in raw_flags
                if isinstance(entry, dict)
                and all(_nonempty_str(entry.get(k)) for k in _REDUNDANCY_KEYS)
            ]

    return CompletenessReport(
        findings, radius, previews, score, rationale, flags, degraded
    )


def _jsonable(obj):
    to_json = getattr(obj, "to_json", None)
    if callable(to_json):
        value = to_json()
        return json.loads(value) if isinstance(value, str) else value
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return vars(obj)


def _render_text(report):
    lines = ["Lint findings:"]
    for f in report.lint_findings:
        lines.append(
            f"  [{_get(f, 'severity')}] {_get(f, 'rule_id')} "
            f"{_get(f, 'file')}:{_get(f, 'line')}: {_get(f, 'message')}"
        )
    lines.append("Predicted blast radius:")
    for cid in report.predicted_blast_radius:
        lines.append(f"  {cid}")
    if report.completeness_score is not None:
        lines.append(f"Completeness score: {report.completeness_score}")
        lines.append(f"  {report.completeness_rationale}")
    lines.append("Redundancy flags:")
    for flag in report.redundancy_flags:
        lines.append(
            f"  {flag['new_requirement']} overlaps {flag['overlaps_with']}: "
            f"{flag['rationale']}"
        )
    lines.append(f"Degraded: {str(report.degraded).lower()}")
    return "\n".join(lines)


def _usage(message):
    print(f"hotdocs assist: {message}", file=sys.stderr)
    print(
        "usage: hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] "
        "[--format=json|text] [--model=<model>]",
        file=sys.stderr,
    )
    return 2


def main(argv):
    changed = []
    repo_root = Path.cwd()
    fmt = "text"
    model = None
    i = 0
    while i < len(argv):
        token = argv[i]
        flag, eq, value = token.partition("=")
        if flag not in _FLAGS:
            return _usage(f"unknown argument: {token}")
        if not eq:
            if i + 1 >= len(argv):
                return _usage(f"{flag} requires a value")
            i += 1
            value = argv[i]
        if flag == "--changed":
            changed.extend(part.strip() for part in value.split(",") if part.strip())
        elif flag == "--repo-root":
            repo_root = Path(value)
        elif flag == "--format":
            fmt = value
        else:
            model = value
        i += 1

    if not changed:
        return _usage("--changed is required")
    if fmt not in ("json", "text"):
        return _usage(f"invalid --format: {fmt}")

    report = assist(changed, repo_root, model)
    if fmt == "json":
        print(json.dumps(report.to_dict(), default=_jsonable, indent=2))
    else:
        print(_render_text(report))
    if any(_get(f, "severity") == "fail" for f in report.lint_findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
