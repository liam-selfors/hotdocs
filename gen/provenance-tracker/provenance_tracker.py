"""provenance-tracker: `hotdocs verify` readiness checks and AttemptRecord history.

Library:
    check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None) -> VerifyReport
    write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root) -> AttemptRecord
    last_requirement_failures(component_id, repo_root) -> list[str]

CLI:
    main(["verify", ...]) / main(["track", "feedback", <component-id>, ...])
"""

import dataclasses
import importlib.util
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class _PlainRecord(dict):
    """A plain JSON-shaped dict whose keys are also readable as attributes."""

    __getattr__ = dict.get


class VerifyReport(_PlainRecord):
    """`interface/data/VerifyReport.md`."""


class AttemptRecord(_PlainRecord):
    """`interface/data/AttemptRecord.md`."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, name):
    """Dual dict-or-attribute access for any value read from a dependency."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _to_plain(value):
    """Recursively convert a value to plain JSON values (R-TRACK-007)."""
    if dataclasses.is_dataclass(value):
        return _to_plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return _to_plain(vars(value))


def _tool_root():
    """The parent of the nearest directory named `gen` above this module."""
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load(slug, module_name, repo_root):
    """Load a dependency module from `repo_root` (or the tool root when absent there)."""
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    flat = directory / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        package_dir = directory / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


def _frontmatter(path):
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    return yaml.safe_load(match.group(1)) or {}


def _corpus_components(repo_root):
    """[(component_id, realizes-list)] for every specs/components/*/component.md."""
    entries = []
    for path in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        frontmatter = _frontmatter(path)
        entries.append((frontmatter["id"], list(frontmatter.get("realizes") or [])))
    return entries


def _component_reasons(component_id, result):
    """Not-ready reasons for a non-sealed component's ProvenanceCheckResult."""
    if not _get(result, "hit"):
        return [
            f"{component_id}: no provenance for current spec state — "
            f"run hotdocs generate {component_id}"
        ]
    reasons = []
    report = _get(result, "verification_report")
    if _get(report, "overall") != "pass":
        requirement_results = _get(report, "requirement_results") or {}
        failing = [rid for rid, status in requirement_results.items() if status == "fail"]
        reasons.append(
            f"{component_id}: verification failed — failing requirements: "
            f"{', '.join(failing)}"
        )
    if _get(_get(result, "license_scan"), "blocked"):
        reasons.append(f"{component_id}: license_scan blocked")
    if _get(_get(result, "secret_scan"), "flagged"):
        reasons.append(f"{component_id}: secret_scan flagged")
    return reasons


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    """Would a merge pass right now (R-TRACK-009/010/011/012)."""
    repo_root = Path(repo_root)
    checker = _load("provenance-checker", "provenance_checker", repo_root)
    corpus = _corpus_components(repo_root)

    if changed_ids:
        scope = "blast-radius"
        analyzer = _load("impact-analyzer", "impact_analyzer", repo_root)
        blast = analyzer.compute_blast_radius(list(changed_ids), repo_root)
        component_ids = [_get(entry, "component_id") for entry in _get(blast, "impacted")]
    else:
        scope = "whole-corpus"
        component_ids = [component_id for component_id, _ in corpus]

    components = {}
    reasons = []
    for component_id in component_ids:
        sealed_key = checker.current_sealed_key(component_id, repo_root)
        if sealed_key is None:
            key = checker.current_provenance_key(component_id, repo_root)
            result = checker.check_provenance(
                component_id,
                _get(key, "spec_bundle_hash"),
                _get(key, "gate_versions"),
                repo_root,
            )
            components[component_id] = result
            reasons.extend(_component_reasons(component_id, result))
        else:
            result = checker.check_sealed_provenance(component_id, repo_root)
            components[component_id] = result
            if not _get(result, "hit"):
                reasons.append(
                    f"{component_id}: sealed provenance {_get(result, 'reason')} — "
                    f"run hotdocs generate {component_id}"
                )

    scope_ids = set(component_ids)
    realized_by = {}
    for component_id, realizes in corpus:
        for capability_id in realizes:
            realized_by.setdefault(capability_id, set()).add(component_id)
    intersecting = sorted(
        capability_id
        for capability_id, realizers in realized_by.items()
        if realizers & scope_ids
    )

    capabilities = {}
    if intersecting:
        verifier = _load(
            "capability-scenario-verifier", "capability_scenario_verifier", repo_root
        )
        for capability_id in intersecting:
            result = verifier.check_capability_provenance(capability_id, repo_root)
            if not _get(result, "hit"):
                if model is None:
                    raise ValueError(
                        f"capability {capability_id} needs a fresh run but no model was given"
                    )
                result = verifier.run_capability_gates(
                    capability_id, repo_root, model, seed, llm_backend
                )
            capabilities[capability_id] = result
            report = _get(result, "capability_scenario_report")
            if _get(_get(report, capability_id), "overall") != "pass":
                reasons.append(f"{capability_id}: capability scenarios did not pass")

    return VerifyReport(
        scope=scope,
        ready=not reasons,
        components=components,
        capabilities=capabilities,
        not_ready_reasons=reasons,
    )


def write_attempt_record(
    component_id, generation_result, verification_report, spec_bundle_hash, repo_root
):
    """Write one AttemptRecord under .hotdocs/attempts/<component_id>/ (R-TRACK-007)."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{now.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}-{secrets.token_hex(3)}"
    record = AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=_to_plain(generation_result),
        verification=_to_plain(verification_report),
    )
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=2))
    return record


def last_requirement_failures(component_id, repo_root):
    """Failing R-ids of the most recent AttemptRecord with a verification (R-TRACK-008)."""
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    for path in sorted(directory.glob("*.json"), key=lambda p: p.name, reverse=True):
        record = json.loads(path.read_text(encoding="utf-8"))
        verification = record.get("verification")
        if verification is not None:
            return [
                rid
                for rid, status in verification["requirement_results"].items()
                if status == "fail"
            ]
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse(args, flags):
    """Parse `--flag=value` / `--flag value` arguments; every flag may repeat."""
    values = {}
    positionals = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg.startswith("--"):
            name, equals, value = arg[2:].partition("=")
            if name not in flags:
                raise _UsageError(f"unknown argument: {arg}")
            if not equals:
                index += 1
                if index >= len(args):
                    raise _UsageError(f"--{name} needs a value")
                value = args[index]
            values.setdefault(name, []).append(value)
        else:
            positionals.append(arg)
        index += 1
    return values, positionals


def _verify(args):
    values, positionals = _parse(args, ("changed", "model", "seed", "repo-root", "format"))
    if positionals:
        raise _UsageError(f"unknown argument: {positionals[0]}")
    try:
        seed = int(values.get("seed", ["0"])[-1])
    except ValueError:
        raise _UsageError("--seed must be an integer")
    output_format = values.get("format", ["text"])[-1]
    if output_format not in ("text", "json"):
        raise _UsageError(f"invalid --format: {output_format}")
    repo_root = Path(values["repo-root"][-1]) if "repo-root" in values else Path.cwd()
    try:
        report = check_readiness(
            repo_root,
            changed_ids=values.get("changed"),
            model=values.get("model", [None])[-1],
            seed=seed,
        )
    except ValueError as exc:
        raise _UsageError(str(exc))
    ready = _get(report, "ready")
    if output_format == "json":
        print(json.dumps(_to_plain(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons"):
            print(reason)
    return 0 if ready else 1


def _feedback(args):
    values, positionals = _parse(args, ("repo-root",))
    if len(positionals) != 1:
        raise _UsageError("expected exactly one <component-id>")
    repo_root = Path(values["repo-root"][-1]) if "repo-root" in values else Path.cwd()
    failures = last_requirement_failures(positionals[0], repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv):
    try:
        if argv[:1] == ["verify"]:
            return _verify(argv[1:])
        if argv[:2] == ["track", "feedback"]:
            return _feedback(argv[2:])
        raise _UsageError("expected 'verify' or 'track feedback'")
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
