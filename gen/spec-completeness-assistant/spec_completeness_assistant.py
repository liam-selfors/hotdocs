"""Spec Completeness Assistant.

Advisory-only helper for a developer landing a spec change: runs cheap
deterministic checks first (lint, blast radius), then a hint-mode
preview, then (with a model configured) judgment-based completeness and
redundancy checks. Never gates anything (R-ASSIST-006).
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# dual dict-or-attribute access helpers
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_plain(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    if dataclasses.is_dataclass(obj):
        return {f.name: _to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items()}
    return obj


# ---------------------------------------------------------------------------
# dependency loading
# ---------------------------------------------------------------------------

def _load_module(repo_root: Path, slug: str, module_name: str):
    base = Path(repo_root) / "gen" / slug
    pkg_init = base / module_name / "__init__.py"
    flat = base / f"{module_name}.py"

    if pkg_init.exists():
        path = pkg_init
        search_locations = [str(path.parent)]
    elif flat.exists():
        path = flat
        search_locations = None
    else:
        raise ImportError(f"cannot find dependency module {module_name!r} under {base}")

    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CompletenessReport:
    lint_findings: list = dataclasses.field(default_factory=list)
    predicted_blast_radius: list = dataclasses.field(default_factory=list)
    hint_previews: dict = dataclasses.field(default_factory=dict)
    completeness_score: float | None = None
    completeness_rationale: str | None = None
    redundancy_flags: list = dataclasses.field(default_factory=list)
    degraded: bool = False


# ---------------------------------------------------------------------------
# model-call parsing (R-ASSIST-010)
# ---------------------------------------------------------------------------

def _unwrap_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_completeness_response(response):
    error = _get(response, "model_call_error")
    text = _get(response, "text")
    if error is not None or not text:
        return None, None
    try:
        data = json.loads(_unwrap_code_fence(text))
    except (ValueError, TypeError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    score = data.get("completeness_score")
    rationale = data.get("completeness_rationale")
    if score is None or not isinstance(rationale, str) or not rationale:
        return None, None
    try:
        score = float(score)
    except (TypeError, ValueError):
        return None, None
    score = max(0.0, min(1.0, score))
    return score, rationale


def _parse_redundancy_response(response):
    error = _get(response, "model_call_error")
    text = _get(response, "text")
    if error is not None or not text:
        return []
    try:
        data = json.loads(_unwrap_code_fence(text))
    except (ValueError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    flags = data.get("redundancy_flags")
    if not isinstance(flags, list):
        return []
    result = []
    for entry in flags:
        if not isinstance(entry, dict):
            continue
        new_requirement = entry.get("new_requirement")
        overlaps_with = entry.get("overlaps_with")
        rationale = entry.get("rationale")
        if not new_requirement or not overlaps_with or not rationale:
            continue
        result.append(
            {
                "new_requirement": new_requirement,
                "overlaps_with": overlaps_with,
                "rationale": rationale,
            }
        )
    return result


def _build_completeness_prompt(changed_ids, lint_findings, hint_previews) -> str:
    lines = [
        "You are assessing the completeness of a draft spec change.",
        "Changed ids: " + ", ".join(changed_ids),
        "",
        "Lint findings:",
    ]
    for f in lint_findings:
        lines.append(f"- {_get(f, 'rule_id')} ({_get(f, 'severity')}): {_get(f, 'message')}")
    lines.append("")
    lines.append("Hint-mode previews of components in the predicted blast radius:")
    for component_id in hint_previews:
        lines.append(f"- {component_id}")
    lines.append("")
    lines.append(
        "Assess: whether touched requirements have present, non-trivial "
        "acceptance criteria; whether a dependent's interface/ content looks "
        "like it needs a matching update that wasn't made; whether the "
        "change's Definitions entries conflict with the glossary."
    )
    lines.append(
        "Respond with exactly this JSON shape, no prose, no code fence: "
        '{"completeness_score": <0.0-1.0>, "completeness_rationale": "<text>"}'
    )
    return "\n".join(lines)


def _build_redundancy_prompt(changed_ids, hint_previews) -> str:
    lines = [
        "You are checking whether a draft spec change restates behavior "
        "already specified elsewhere in the corpus.",
        "Changed ids: " + ", ".join(changed_ids),
        "",
        "Hint-mode previews of components in the predicted blast radius:",
    ]
    for component_id in hint_previews:
        lines.append(f"- {component_id}")
    lines.append("")
    lines.append(
        "Respond with exactly this JSON shape, no prose, no code fence: "
        '{"redundancy_flags": [{"new_requirement": "R-id", '
        '"overlaps_with": "R-id", "rationale": "<text>"}]}'
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# library entry point
# ---------------------------------------------------------------------------

def assist(changed_ids, repo_root, model=None, *, llm_backend=None) -> CompletenessReport:
    repo_root = Path(repo_root)

    spec_linter = _load_module(repo_root, "spec-linter", "spec_linter")

    lint_report = spec_linter.lint(None, repo_root)
    raw_findings = _get(lint_report, "findings", [])
    lint_findings = [_to_plain(f) for f in raw_findings]

    if any(_get(f, "severity") == "fail" for f in raw_findings):
        return CompletenessReport(
            lint_findings=lint_findings,
            predicted_blast_radius=[],
            hint_previews={},
            completeness_score=None,
            completeness_rationale=None,
            redundancy_flags=[],
            degraded=(model is None),
        )

    impact_analyzer = _load_module(repo_root, "impact-analyzer", "impact_analyzer")
    spec_bundle_assembler = _load_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")

    blast_radius_report = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
    impacted = _get(blast_radius_report, "impacted", [])
    predicted_blast_radius = [_get(entry, "component_id") for entry in impacted]

    generator_mod = None
    if model is not None:
        generator_mod = _load_module(repo_root, "generator", "generator")

    hint_previews = {}
    for component_id in predicted_blast_radius:
        bundle = spec_bundle_assembler.assemble(component_id, repo_root=repo_root, mode="hint")
        if model is not None:
            gen_result = generator_mod.generate(
                bundle, model, None, repo_root=repo_root, llm_backend=llm_backend
            )
            hint_previews[component_id] = _to_plain(gen_result)
        else:
            hint_previews[component_id] = _to_plain(bundle)

    completeness_score = None
    completeness_rationale = None
    redundancy_flags: list = []
    degraded = model is None

    if model is not None:
        llm_endpoint = _load_module(repo_root, "llm-endpoint", "llm_endpoint")

        completeness_prompt = _build_completeness_prompt(changed_ids, lint_findings, hint_previews)
        completeness_response = llm_endpoint.complete(completeness_prompt, model, backend=llm_backend)
        completeness_score, completeness_rationale = _parse_completeness_response(completeness_response)

        redundancy_prompt = _build_redundancy_prompt(changed_ids, hint_previews)
        redundancy_response = llm_endpoint.complete(redundancy_prompt, model, backend=llm_backend)
        redundancy_flags = _parse_redundancy_response(redundancy_response)

    return CompletenessReport(
        lint_findings=lint_findings,
        predicted_blast_radius=predicted_blast_radius,
        hint_previews=hint_previews,
        completeness_score=completeness_score,
        completeness_rationale=completeness_rationale,
        redundancy_flags=redundancy_flags,
        degraded=degraded,
    )


# ---------------------------------------------------------------------------
# CLI (R-ASSIST-009)
# ---------------------------------------------------------------------------

def _print_text(report: CompletenessReport) -> None:
    print("Lint findings:")
    if report.lint_findings:
        for finding in report.lint_findings:
            print(f"  {_get(finding, 'rule_id')} ({_get(finding, 'severity')}): {_get(finding, 'message')}")
    else:
        print("  (none)")

    print("Predicted blast radius:")
    if report.predicted_blast_radius:
        for component_id in report.predicted_blast_radius:
            print(f"  {component_id}")
    else:
        print("  (none)")

    if report.completeness_score is not None:
        print(f"Completeness score: {report.completeness_score}")

    if report.degraded:
        print("degraded: true (no model configured)")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = list(argv)
    if args and args[0] == "assist":
        args = args[1:]

    changed: list[str] = []
    repo_root = Path.cwd()
    fmt = "text"
    model = None

    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("--"):
            print(f"usage error: unexpected argument {arg!r}", file=sys.stderr)
            return 2

        if "=" in arg:
            key, value = arg[2:].split("=", 1)
            i += 1
        else:
            key = arg[2:]
            if i + 1 >= len(args):
                print(f"usage error: --{key} requires a value", file=sys.stderr)
                return 2
            value = args[i + 1]
            i += 2

        if key == "changed":
            changed.extend(v for v in value.split(",") if v)
        elif key == "repo-root":
            repo_root = Path(value)
        elif key == "format":
            fmt = value
        elif key == "model":
            model = value
        else:
            print(f"usage error: unknown argument --{key}", file=sys.stderr)
            return 2

    if not changed:
        print("usage error: --changed is required", file=sys.stderr)
        return 2

    if fmt not in ("json", "text"):
        print(f"usage error: invalid --format {fmt!r}", file=sys.stderr)
        return 2

    report = assist(changed, repo_root, model)

    if fmt == "json":
        print(json.dumps(_to_plain(report), indent=2))
    else:
        _print_text(report)

    if any(_get(f, "severity") == "fail" for f in report.lint_findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())