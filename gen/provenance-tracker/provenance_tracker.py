from __future__ import annotations

import dataclasses
import importlib.util
import itertools
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

_LOAD_COUNTER = itertools.count()


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError("provenance_tracker.py must live under a 'gen' directory")


def _dependency_dir(repo_root: Path, dep_slug: str) -> Path:
    candidate = repo_root / "gen" / dep_slug
    if candidate.is_dir():
        return candidate
    return _tool_root() / "gen" / dep_slug


def _load_dependency_module(repo_root: Path, dep_slug: str, module_name: str):
    base = _dependency_dir(Path(repo_root), dep_slug)
    flat_path = base / f"{module_name}.py"
    pkg_path = base / module_name / "__init__.py"
    if flat_path.is_file():
        path = flat_path
    elif pkg_path.is_file():
        path = pkg_path
    else:
        raise ImportError(f"cannot find module {module_name!r} under {base}")
    unique_name = (
        f"_provenance_tracker_dep_{dep_slug.replace('-', '_')}_"
        f"{module_name}_{next(_LOAD_COUNTER)}"
    )
    spec = importlib.util.spec_from_file_location(unique_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data or {}


def _discover_all_component_ids(repo_root: Path) -> list:
    base = Path(repo_root) / "specs" / "components"
    ids = []
    if not base.is_dir():
        return ids
    for child in sorted(base.iterdir()):
        comp_md = child / "component.md"
        if not comp_md.is_file():
            continue
        frontmatter = _parse_frontmatter(comp_md)
        comp_id = frontmatter.get("id")
        if comp_id:
            ids.append(comp_id)
    return sorted(ids)


def _discover_realizes(repo_root: Path) -> dict:
    base = Path(repo_root) / "specs" / "components"
    mapping: dict = {}
    if not base.is_dir():
        return mapping
    for child in sorted(base.iterdir()):
        comp_md = child / "component.md"
        if not comp_md.is_file():
            continue
        frontmatter = _parse_frontmatter(comp_md)
        comp_id = frontmatter.get("id")
        if not comp_id:
            continue
        for capability_id in frontmatter.get("realizes") or []:
            mapping.setdefault(capability_id, set()).add(comp_id)
    return mapping


def _to_plain(value):
    if value is None:
        return None
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _to_plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return _to_plain(vars(value))
    return value


@dataclass
class VerifyReport:
    scope: str
    ready: bool
    components: dict
    capabilities: dict
    not_ready_reasons: list = field(default_factory=list)


@dataclass
class AttemptRecord:
    attempt_id: str
    component_id: str
    timestamp: str
    spec_bundle_hash: str
    generation: Any
    verification: Any


def check_readiness(
    repo_root: Path,
    changed_ids: Optional[list] = None,
    model: Optional[str] = None,
    seed: int = 0,
    llm_backend=None,
) -> VerifyReport:
    repo_root = Path(repo_root)
    provenance_checker = _load_dependency_module(
        repo_root, "provenance-checker", "provenance_checker"
    )

    if changed_ids:
        impact_analyzer = _load_dependency_module(
            repo_root, "impact-analyzer", "impact_analyzer"
        )
        blast_report = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
        impacted = _get(blast_report, "impacted") or []
        component_ids = sorted({_get(entry, "component_id") for entry in impacted})
        scope = "blast-radius"
    else:
        component_ids = _discover_all_component_ids(repo_root)
        scope = "whole-corpus"

    components: dict = {}
    not_ready_reasons: list = []
    ready = True

    for component_id in component_ids:
        sealed_key = provenance_checker.current_sealed_key(component_id, repo_root)
        if sealed_key is not None:
            result = provenance_checker.check_sealed_provenance(component_id, repo_root)
            components[component_id] = result
            if not _get(result, "hit"):
                ready = False
                reason = _get(result, "reason")
                not_ready_reasons.append(
                    f"{component_id}: sealed provenance {reason} — "
                    f"run hotdocs generate {component_id}"
                )
            continue

        key = provenance_checker.current_provenance_key(component_id, repo_root)
        spec_bundle_hash = _get(key, "spec_bundle_hash")
        gate_versions = _get(key, "gate_versions")
        result = provenance_checker.check_provenance(
            component_id, spec_bundle_hash, gate_versions, repo_root
        )
        components[component_id] = result
        if not _get(result, "hit"):
            ready = False
            not_ready_reasons.append(
                f"{component_id}: no provenance for current spec state — "
                f"run hotdocs generate {component_id}"
            )
            continue

        verification_report = _get(result, "verification_report")
        if _get(verification_report, "overall") != "pass":
            ready = False
            requirement_results = _get(verification_report, "requirement_results") or {}
            failing = sorted(r for r, v in requirement_results.items() if v == "fail")
            detail = f" ({', '.join(failing)})" if failing else ""
            not_ready_reasons.append(f"{component_id}: verification failing{detail}")

        license_scan = _get(result, "license_scan")
        if _get(license_scan, "blocked"):
            ready = False
            not_ready_reasons.append(f"{component_id}: license_scan blocked")

        secret_scan = _get(result, "secret_scan")
        if _get(secret_scan, "flagged"):
            ready = False
            not_ready_reasons.append(f"{component_id}: secret_scan flagged")

    realizes_map = _discover_realizes(repo_root)
    scope_set = set(component_ids)
    intersecting_capability_ids = sorted(
        capability_id
        for capability_id, comps in realizes_map.items()
        if comps & scope_set
    )

    capabilities: dict = {}
    capability_scenario_verifier = None
    for capability_id in intersecting_capability_ids:
        if capability_scenario_verifier is None:
            capability_scenario_verifier = _load_dependency_module(
                repo_root, "capability-scenario-verifier", "capability_scenario_verifier"
            )
        check_result = capability_scenario_verifier.check_capability_provenance(
            capability_id, repo_root
        )
        if _get(check_result, "hit"):
            result = check_result
        else:
            if model is None:
                raise ValueError(
                    f"capability {capability_id} requires a fresh run but no model was given"
                )
            result = capability_scenario_verifier.run_capability_gates(
                capability_id, repo_root, model, seed, llm_backend
            )
        capabilities[capability_id] = result

        report = _get(result, "capability_scenario_report")
        entry = _get(report, capability_id)
        if _get(entry, "overall") != "pass":
            ready = False
            not_ready_reasons.append(
                f"{capability_id}: capability scenario verification failing"
            )

    return VerifyReport(
        scope=scope,
        ready=ready,
        components=components,
        capabilities=capabilities,
        not_ready_reasons=not_ready_reasons,
    )


def write_attempt_record(
    component_id: str,
    generation_result,
    verification_report,
    spec_bundle_hash: str,
    repo_root: Path,
) -> AttemptRecord:
    repo_root = Path(repo_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{uuid.uuid4().hex[:6]}"

    generation_plain = _to_plain(generation_result)
    verification_plain = (
        _to_plain(verification_report) if verification_report is not None else None
    )

    record_dict = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": timestamp,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_plain,
        "verification": verification_plain,
    }

    dest_dir = repo_root / ".hotdocs" / "attempts" / component_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{attempt_id}.json"
    dest_path.write_text(json.dumps(record_dict, indent=2, sort_keys=True), encoding="utf-8")

    return AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=generation_plain,
        verification=verification_plain,
    )


def last_requirement_failures(component_id: str, repo_root: Path) -> list:
    repo_root = Path(repo_root)
    dest_dir = repo_root / ".hotdocs" / "attempts" / component_id
    if not dest_dir.is_dir():
        return []
    files = sorted(dest_dir.glob("*.json"))
    for path in reversed(files):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        verification = _get(data, "verification")
        if verification is not None:
            requirement_results = _get(verification, "requirement_results") or {}
            return sorted(r for r, v in requirement_results.items() if v == "fail")
    return []


class _UsageError(Exception):
    pass


def _parse_args(args, flags_with_value, repeatable=frozenset()):
    result: dict = {}
    positionals = []
    i = 0
    n = len(args)
    while i < n:
        arg = args[i]
        if arg.startswith("--"):
            if "=" in arg:
                key, value = arg[2:].split("=", 1)
                if key not in flags_with_value:
                    raise _UsageError(f"unknown flag: --{key}")
            else:
                key = arg[2:]
                if key not in flags_with_value:
                    raise _UsageError(f"unknown flag: --{key}")
                i += 1
                if i >= n:
                    raise _UsageError(f"flag --{key} given with no value")
                value = args[i]
            if key in repeatable:
                result.setdefault(key, []).append(value)
            else:
                result[key] = value
        else:
            positionals.append(arg)
        i += 1
    return result, positionals


def _run_verify(args) -> int:
    opts, positionals = _parse_args(
        args,
        {"changed", "model", "seed", "repo-root", "format"},
        repeatable={"changed"},
    )
    if positionals:
        raise _UsageError(f"unexpected argument: {positionals[0]}")

    fmt = opts.get("format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")

    seed_raw = opts.get("seed", "0")
    try:
        seed = int(seed_raw)
    except ValueError:
        raise _UsageError(f"invalid --seed: {seed_raw}")

    repo_root = Path(opts.get("repo-root", "."))
    model = opts.get("model")
    changed_ids = opts.get("changed")

    try:
        report = check_readiness(
            repo_root, changed_ids=changed_ids, model=model, seed=seed
        )
    except ValueError as exc:
        raise _UsageError(str(exc))

    ready = _get(report, "ready")

    if fmt == "json":
        print(json.dumps(_to_plain(report), indent=2, sort_keys=True))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)

    return 0 if ready else 1


def _run_track_feedback(args) -> int:
    opts, positionals = _parse_args(args, {"repo-root"})
    if not positionals:
        raise _UsageError("missing <component-id>")
    component_id = positionals[0]
    if len(positionals) > 1:
        raise _UsageError(f"unexpected argument: {positionals[1]}")

    repo_root = Path(opts.get("repo-root", "."))
    failures = last_requirement_failures(component_id, repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv: Optional[list] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: hotdocs verify|track feedback ...", file=sys.stderr)
        return 2

    command = argv[0]
    try:
        if command == "verify":
            return _run_verify(argv[1:])
        if command == "track":
            if len(argv) < 2 or argv[1] != "feedback":
                raise _UsageError("expected 'track feedback'")
            return _run_track_feedback(argv[2:])
        raise _UsageError(f"unknown command: {command}")
    except _UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())