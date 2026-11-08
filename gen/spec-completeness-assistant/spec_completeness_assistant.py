from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CompletenessReport:
    lint_findings: list
    predicted_blast_radius: list
    hint_previews: dict
    completeness_score: "float | None"
    completeness_rationale: "str | None"
    redundancy_flags: list
    degraded: bool


class _UsageError(Exception):
    pass


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _asdict_safe(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _asdict_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_asdict_safe(v) for v in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: _asdict_safe(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
        }
    return obj


def _finding_to_dict(f):
    if isinstance(f, dict):
        return dict(f)
    if dataclasses.is_dataclass(f) and not isinstance(f, type):
        return dataclasses.asdict(f)
    d = {}
    for field in ("rule_id", "severity", "file", "line", "message", "rationale"):
        if hasattr(f, field):
            d[field] = getattr(f, field)
    return d


# ---------------------------------------------------------------------------
# Dependency loading (R-ASSIST-011)
# ---------------------------------------------------------------------------

_LOADED_MODULES = {}


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError(
        "spec-completeness-assistant: could not locate tool root "
        "(no ancestor directory named 'gen')"
    )


def _dependency_dir(repo_root, slug):
    repo_root = Path(repo_root)
    candidate = repo_root / "gen" / slug
    if candidate.is_dir():
        return candidate
    return _tool_root() / "gen" / slug


def _load_dependency(repo_root, slug, module_name):
    dep_dir = _dependency_dir(repo_root, slug)
    flat_path = dep_dir / f"{module_name}.py"
    pkg_init = dep_dir / module_name / "__init__.py"

    if flat_path.is_file():
        load_path = flat_path
        submodule_locations = None
    elif pkg_init.is_file():
        load_path = pkg_init
        submodule_locations = [str(pkg_init.parent)]
    else:
        raise ImportError(
            f"could not locate dependency module {module_name!r} for "
            f"{slug!r} under {dep_dir}"
        )

    cache_key = str(load_path.resolve())
    cached = _LOADED_MODULES.get(cache_key)
    if cached is not None:
        return cached

    reg_name = f"_hotdocs_dep_{slug.replace('-', '_')}__{abs(hash(cache_key))}"
    if submodule_locations is not None:
        spec = importlib.util.spec_from_file_location(
            reg_name, str(load_path), submodule_search_locations=submodule_locations
        )
    else:
        spec = importlib.util.spec_from_file_location(reg_name, str(load_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[reg_name] = module
    spec.loader.exec_module(module)
    _LOADED_MODULES[cache_key] = module
    return module


# ---------------------------------------------------------------------------
# Model-response parsing (R-ASSIST-010)
# ---------------------------------------------------------------------------

def _unwrap_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_completeness(text):
    if not text:
        return None, None
    try:
        data = json.loads(_unwrap_code_fence(text))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    if "completeness_score" not in data or "completeness_rationale" not in data:
        return None, None
    score = data["completeness_score"]
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None, None
    rationale = data["completeness_rationale"]
    if not isinstance(rationale, str) or rationale == "":
        return None, None
    score = max(0.0, min(1.0, float(score)))
    return score, rationale


def _parse_redundancy(text):
    if not text:
        return []
    try:
        data = json.loads(_unwrap_code_fence(text))
    except (json.JSONDecodeError, TypeError, ValueError):
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
        new_req = entry.get("new_requirement")
        overlaps = entry.get("overlaps_with")
        rationale = entry.get("rationale")
        if not isinstance(new_req, str) or not new_req:
            continue
        if not isinstance(overlaps, str) or not overlaps:
            continue
        if not isinstance(rationale, str) or not rationale:
            continue
        result.append(
            {
                "new_requirement": new_req,
                "overlaps_with": overlaps,
                "rationale": rationale,
            }
        )
    return result


def _build_completeness_prompt(changed_ids, predicted_blast_radius, lint_findings, hint_previews):
    return (
        "You are assessing the completeness of a draft spec change before "
        "it is submitted to the real merge pipeline.\n\n"
        f"Changed requirement ids: {json.dumps(list(changed_ids))}\n"
        f"Predicted blast radius (impacted components): "
        f"{json.dumps(predicted_blast_radius)}\n"
        f"Lint findings against the draft: {json.dumps(lint_findings, default=str)}\n"
        f"Hint-mode previews for impacted components: "
        f"{json.dumps(hint_previews, default=str)}\n\n"
        "Judge completeness considering: (1) whether the touched "
        "requirements have present, non-trivial acceptance criteria; "
        "(2) whether a dependent's interface/ content looks like it "
        "needs a matching update that was not made; (3) whether the "
        "change's Definitions entries conflict with the glossary (build "
        "on, rather than re-detect, the glossary-conformance lint "
        "findings above).\n\n"
        "Respond with ONLY JSON of exactly this shape, no surrounding "
        "prose:\n"
        '{"completeness_score": 0.0, "completeness_rationale": "..."}'
    )


def _build_redundancy_prompt(changed_ids, predicted_blast_radius, hint_previews):
    return (
        "You are checking whether a draft spec change restates behavior "
        "already specified elsewhere in the corpus (semantic overlap, not "
        "structural duplication).\n\n"
        f"Changed requirement ids: {json.dumps(list(changed_ids))}\n"
        f"Predicted blast radius (impacted components): "
        f"{json.dumps(predicted_blast_radius)}\n"
        f"Hint-mode previews for impacted components: "
        f"{json.dumps(hint_previews, default=str)}\n\n"
        "For each changed requirement id that restates behavior already "
        "specified by a different, pre-existing requirement, report an "
        "overlap. Only include entries for a real judgment call that "
        "actually fired.\n\n"
        "Respond with ONLY JSON of exactly this shape, no surrounding "
        "prose:\n"
        '{"redundancy_flags": [{"new_requirement": "R-id", '
        '"overlaps_with": "R-id", "rationale": "..."}]}'
    )


# ---------------------------------------------------------------------------
# Library entry point
# ---------------------------------------------------------------------------

def assist(changed_ids, repo_root, model=None, *, llm_backend=None):
    repo_root = Path(repo_root)
    degraded = model is None

    spec_linter = _load_dependency(repo_root, "spec-linter", "spec_linter")
    lint_report = spec_linter.lint(None, repo_root)
    raw_findings = _get(lint_report, "findings", []) or []
    lint_findings = [_finding_to_dict(f) for f in raw_findings]
    has_hard_fail = any(_get(f, "severity") == "fail" for f in raw_findings)

    if has_hard_fail:
        return CompletenessReport(
            lint_findings=lint_findings,
            predicted_blast_radius=[],
            hint_previews={},
            completeness_score=None,
            completeness_rationale=None,
            redundancy_flags=[],
            degraded=degraded,
        )

    impact_analyzer = _load_dependency(repo_root, "impact-analyzer", "impact_analyzer")
    blast_report = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
    impacted = _get(blast_report, "impacted", []) or []
    predicted_blast_radius = [_get(entry, "component_id") for entry in impacted]

    spec_bundle_assembler = _load_dependency(
        repo_root, "spec-bundle-assembler", "spec_bundle_assembler"
    )
    generator = None
    if model is not None:
        generator = _load_dependency(repo_root, "generator", "generator")

    hint_previews = {}
    for component_id in predicted_blast_radius:
        bundle = spec_bundle_assembler.assemble(component_id, repo_root=repo_root, mode="hint")
        if model is not None:
            gen_result = generator.generate(
                bundle, model, None, repo_root=repo_root, llm_backend=llm_backend
            )
            hint_previews[component_id] = _asdict_safe(gen_result)
        else:
            hint_previews[component_id] = _asdict_safe(bundle)

    completeness_score = None
    completeness_rationale = None
    redundancy_flags = []

    if model is not None:
        llm_endpoint = _load_dependency(repo_root, "llm-endpoint", "llm_endpoint")

        completeness_prompt = _build_completeness_prompt(
            changed_ids, predicted_blast_radius, lint_findings, hint_previews
        )
        response1 = llm_endpoint.complete(completeness_prompt, model, backend=llm_backend)
        if _get(response1, "model_call_error") is None:
            completeness_score, completeness_rationale = _parse_completeness(
                _get(response1, "text")
            )

        redundancy_prompt = _build_redundancy_prompt(
            changed_ids, predicted_blast_radius, hint_previews
        )
        response2 = llm_endpoint.complete(redundancy_prompt, model, backend=llm_backend)
        if _get(response2, "model_call_error") is None:
            redundancy_flags = _parse_redundancy(_get(response2, "text"))

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

_KNOWN_FLAGS = ("--changed", "--repo-root", "--format", "--model")


def _parse_args(argv):
    changed_ids = []
    repo_root = None
    fmt = "text"
    model = None
    seen_changed = False

    i = 0
    n = len(argv)

    while i < n:
        arg = argv[i]
        flag = None
        value = None

        if "=" in arg:
            candidate_flag = arg.split("=", 1)[0]
            if candidate_flag in _KNOWN_FLAGS:
                flag = candidate_flag
                value = arg.split("=", 1)[1]
                i += 1

        if flag is None:
            flag = arg
            if flag not in _KNOWN_FLAGS:
                raise _UsageError(f"unknown argument {arg!r}")
            if i + 1 >= n:
                raise _UsageError(f"{flag} requires a value")
            value = argv[i + 1]
            i += 2

        if flag == "--changed":
            parts = [p.strip() for p in value.split(",") if p.strip()]
            changed_ids.extend(parts)
            seen_changed = True
        elif flag == "--repo-root":
            repo_root = value
        elif flag == "--format":
            fmt = value
        elif flag == "--model":
            model = value

    if not seen_changed or not changed_ids:
        raise _UsageError("--changed is required")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt!r}")

    return changed_ids, repo_root, fmt, model


def _render_text(report):
    lines = ["Lint findings:"]
    if report.lint_findings:
        for f in report.lint_findings:
            rule_id = f.get("rule_id")
            severity = f.get("severity")
            message = f.get("message")
            lines.append(f"  - {rule_id} [{severity}] {message}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Predicted blast radius:")
    if report.predicted_blast_radius:
        for component_id in report.predicted_blast_radius:
            lines.append(f"  - {component_id}")
    else:
        lines.append("  (none)")

    if report.completeness_score is not None:
        lines.append("")
        lines.append(f"Completeness score: {report.completeness_score}")
        if report.completeness_rationale:
            lines.append(f"Completeness rationale: {report.completeness_rationale}")

    if report.degraded:
        lines.append("")
        lines.append("(degraded: no model configured)")

    return "\n".join(lines)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    try:
        changed_ids, repo_root_str, fmt, model = _parse_args(argv)
    except _UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    repo_root = Path(repo_root_str) if repo_root_str else Path.cwd()

    report = assist(changed_ids, repo_root, model=model)

    if fmt == "json":
        print(json.dumps(dataclasses.asdict(report), indent=2, default=str))
    else:
        print(_render_text(report))

    has_hard_fail = any(f.get("severity") == "fail" for f in report.lint_findings)
    return 1 if has_hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())