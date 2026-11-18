"""Spec Completeness Assistant (comp-spec-completeness-assistant).

Advisory only (R-ASSIST-006): nothing here can block a merge. The report is
returned to the caller and never fed into any gate.
"""

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

__all__ = ["assist", "main"]


# --------------------------------------------------------------------------
# Dependency loading (R-ASSIST-011)
# --------------------------------------------------------------------------

def _tool_root():
    gen = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen.parent


def _load(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / (module_name + ".py")
    if path.is_file():
        spec = importlib.util.spec_from_file_location(module_name, path)
    else:
        path = base / module_name / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            module_name, path, submodule_search_locations=[str(path.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _jsonable(obj):
    return dataclasses.asdict(obj)


# --------------------------------------------------------------------------
# Model-response parsing (R-ASSIST-010)
# --------------------------------------------------------------------------

_FENCE = re.compile(r"^```[^\n]*\n(.*?)\n?```$", re.DOTALL)


def _parse_json(response):
    if _get(response, "model_call_error"):
        return None
    text = _get(response, "text")
    if not isinstance(text, str):
        return None
    text = text.strip()
    match = _FENCE.match(text)
    if match:
        text = match.group(1)
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _parse_completeness(response):
    data = _parse_json(response)
    if data is None:
        return None, None
    score = data.get("completeness_score")
    rationale = data.get("completeness_rationale")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None, None
    if not isinstance(rationale, str) or not rationale.strip():
        return None, None
    return min(1.0, max(0.0, float(score))), rationale


_FLAG_KEYS = ("new_requirement", "overlaps_with", "rationale")


def _parse_redundancy(response):
    data = _parse_json(response)
    if data is None:
        return []
    entries = data.get("redundancy_flags")
    if not isinstance(entries, list):
        return []
    flags = []
    for entry in entries:
        if isinstance(entry, dict) and all(entry.get(k) for k in _FLAG_KEYS):
            flags.append({k: entry[k] for k in _FLAG_KEYS})
    return flags


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

def _bundle_text(bundles):
    parts = []
    for cid, bundle in bundles.items():
        parts.append(
            "### {}\n\n#### SPEC\n{}\n\n#### INTERFACE\n{}".format(
                cid, _get(bundle, "spec"), _get(bundle, "interface")
            )
        )
    return "\n\n".join(parts)


def _corpus_requirements(repo_root):
    parts = []
    for path in sorted((Path(repo_root) / "specs" / "components").glob("*/requirements/*.md")):
        parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts)


def _completeness_prompt(changed_ids, findings, blast_radius, bundles):
    return (
        "You are assessing whether a draft spec change is complete.\n"
        "Judge: whether touched requirements have present, non-trivial "
        "acceptance criteria; whether a dependent's interface/ content looks "
        "like it needs a matching update that wasn't made; whether the "
        "change's Definitions entries conflict with the glossary (the "
        "spec-linter findings below, including R-LINT-011/015, are already "
        "computed -- surface them and add your own broader judgment).\n\n"
        "Changed spec ids: {}\n\n"
        "spec-linter findings:\n{}\n\n"
        "Predicted blast radius: {}\n\n"
        "Impacted component bundles:\n{}\n\n"
        "Reply with only JSON of exactly this shape:\n"
        '{{"completeness_score": <number 0.0-1.0>, '
        '"completeness_rationale": "<structured rationale>"}}\n'
    ).format(
        json.dumps(changed_ids),
        json.dumps(findings, default=_jsonable, indent=2),
        json.dumps(blast_radius),
        _bundle_text(bundles),
    )


def _redundancy_prompt(changed_ids, bundles, repo_root):
    return (
        "You are checking whether a draft spec change restates behavior "
        "already specified elsewhere in the corpus, even if worded "
        "differently.\n\n"
        "Changed spec ids (the draft's own R-ids): {}\n\n"
        "Impacted component bundles:\n{}\n\n"
        "All requirements in the corpus:\n{}\n\n"
        "Reply with only JSON of exactly this shape, listing only real "
        "overlaps (an empty list if none):\n"
        '{{"redundancy_flags": [{{"new_requirement": "<changed R-id>", '
        '"overlaps_with": "<pre-existing R-id>", "rationale": "<why>"}}]}}\n'
    ).format(
        json.dumps(changed_ids),
        _bundle_text(bundles),
        _corpus_requirements(repo_root),
    )


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------

def _has_fail(findings):
    return any(_get(f, "severity") == "fail" for f in findings)


def assist(changed_ids, repo_root, model=None, *, llm_backend=None):
    """Produce an advisory CompletenessReport for a draft spec change."""
    repo_root = Path(repo_root)
    report = {
        "lint_findings": [],
        "predicted_blast_radius": [],
        "hint_previews": {},
        "completeness_score": None,
        "completeness_rationale": None,
        "redundancy_flags": [],
        "degraded": model is None,
    }

    # R-ASSIST-001: cheap deterministic gate first, stopping on hard fail.
    spec_linter = _load("spec-linter", "spec_linter", repo_root)
    lint_report = spec_linter.lint(None, repo_root)
    findings = list(_get(lint_report, "findings"))
    report["lint_findings"] = findings
    if _has_fail(findings):
        return report

    # R-ASSIST-002: predicted blast radius.
    impact_analyzer = _load("impact-analyzer", "impact_analyzer", repo_root)
    blast = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
    radius = [_get(entry, "component_id") for entry in _get(blast, "impacted")]
    report["predicted_blast_radius"] = radius

    # R-ASSIST-003: hint-mode previews.
    assembler = _load("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    generator = None
    if model is not None:
        generator = _load("generator", "generator", repo_root)
    bundles = {}
    for cid in radius:
        bundle = assembler.assemble(cid, repo_root=repo_root, mode="hint")
        bundles[cid] = bundle
        if generator is None:
            report["hint_previews"][cid] = bundle
        else:
            report["hint_previews"][cid] = generator.generate(
                bundle, model, None, repo_root=repo_root, llm_backend=llm_backend
            )

    # R-ASSIST-007: degraded mode makes no model call.
    if model is None:
        return report

    # R-ASSIST-004/005/010: exactly two calls, completeness then redundancy.
    llm_endpoint = _load("llm-endpoint", "llm_endpoint", repo_root)
    completeness = llm_endpoint.complete(
        _completeness_prompt(list(changed_ids), findings, radius, bundles),
        model,
        backend=llm_backend,
    )
    score, rationale = _parse_completeness(completeness)
    report["completeness_score"] = score
    report["completeness_rationale"] = rationale

    redundancy = llm_endpoint.complete(
        _redundancy_prompt(list(changed_ids), bundles, repo_root),
        model,
        backend=llm_backend,
    )
    report["redundancy_flags"] = _parse_redundancy(redundancy)
    return report


# --------------------------------------------------------------------------
# CLI (R-ASSIST-009)
# --------------------------------------------------------------------------

_USAGE = (
    "usage: hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] "
    "[--format=json|text] [--model=<model>]"
)
_FLAGS = ("--changed", "--repo-root", "--format", "--model")


class _UsageError(Exception):
    pass


def _parse_args(argv):
    changed = []
    repo_root = "."
    fmt = "text"
    model = None
    i = 0
    while i < len(argv):
        token = argv[i]
        name, sep, value = token.partition("=")
        if name not in _FLAGS:
            raise _UsageError("unknown argument: " + token)
        if not sep:
            i += 1
            if i >= len(argv):
                raise _UsageError(name + " requires a value")
            value = argv[i]
        if name == "--changed":
            changed.extend(v for v in value.split(",") if v)
        elif name == "--repo-root":
            repo_root = value
        elif name == "--format":
            fmt = value
        else:
            model = value
        i += 1
    if not changed:
        raise _UsageError("--changed is required")
    if fmt not in ("json", "text"):
        raise _UsageError("invalid --format: " + fmt)
    return changed, Path(repo_root), fmt, model


def _render_text(report):
    lines = ["Lint findings:"]
    for f in report["lint_findings"]:
        lines.append(
            "  {} [{}] {}:{} {}".format(
                _get(f, "rule_id"),
                _get(f, "severity"),
                _get(f, "file"),
                _get(f, "line"),
                _get(f, "message"),
            )
        )
    lines.append("Predicted blast radius:")
    for cid in report["predicted_blast_radius"]:
        lines.append("  " + str(cid))
    if report["completeness_score"] is not None:
        lines.append("Completeness score: {}".format(report["completeness_score"]))
        lines.append("Completeness rationale: {}".format(report["completeness_rationale"]))
    if report["redundancy_flags"]:
        lines.append("Redundancy flags:")
        for flag in report["redundancy_flags"]:
            lines.append(
                "  {} overlaps {}: {}".format(
                    flag["new_requirement"], flag["overlaps_with"], flag["rationale"]
                )
            )
    lines.append("Degraded: {}".format(str(report["degraded"]).lower()))
    return "\n".join(lines)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        changed, repo_root, fmt, model = _parse_args(list(argv))
    except _UsageError as exc:
        print(str(exc), file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    report = assist(changed, repo_root, model)
    if fmt == "json":
        print(json.dumps(report, default=_jsonable, indent=2))
    else:
        print(_render_text(report))
    return 1 if _has_fail(report["lint_findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
