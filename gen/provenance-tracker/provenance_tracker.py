from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml


class _UsageError(Exception):
    pass


@dataclasses.dataclass
class VerifyReport:
    scope: str
    ready: bool
    components: dict
    capabilities: dict
    not_ready_reasons: list


@dataclasses.dataclass
class AttemptRecord:
    attempt_id: str
    component_id: str
    timestamp: str
    spec_bundle_hash: str
    generation: dict
    verification: dict | None


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _to_plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if hasattr(value, "__dict__"):
        return _to_plain(vars(value))
    return value


_loaded_modules_cache: dict = {}


def _load_dependency(repo_root: Path, dep_slug: str, module_name: str):
    repo_root = Path(repo_root)
    cache_key = (str(repo_root.resolve()), dep_slug, module_name)
    if cache_key in _loaded_modules_cache:
        return _loaded_modules_cache[cache_key]

    base = repo_root / "gen" / dep_slug
    flat_path = base / f"{module_name}.py"
    pkg_path = base / module_name / "__init__.py"
    if flat_path.is_file():
        module_path = flat_path
    elif pkg_path.is_file():
        module_path = pkg_path
    else:
        raise ImportError(
            f"could not find dependency module {module_name!r} under {base}"
        )

    unique_name = f"_provenance_tracker_dep_{dep_slug}_{module_name}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(unique_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)

    _loaded_modules_cache[cache_key] = module
    return module


def _parse_frontmatter(component_md_path: Path) -> dict:
    text = component_md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data or {}


def _discover_all_component_ids(repo_root: Path) -> list:
    components_dir = repo_root / "specs" / "components"
    ids = []
    if components_dir.is_dir():
        for sub in sorted(components_dir.iterdir()):
            component_md = sub / "component.md"
            if component_md.is_file():
                frontmatter = _parse_frontmatter(component_md)
                component_id = frontmatter.get("id")
                if component_id:
                    ids.append(component_id)
    return ids


def _capabilities_intersecting(repo_root: Path, component_ids) -> list:
    components_dir = repo_root / "specs" / "components"
    capability_to_realizing: dict = {}
    if components_dir.is_dir():
        for sub in sorted(components_dir.iterdir()):
            component_md = sub / "component.md"
            if not component_md.is_file():
                continue
            frontmatter = _parse_frontmatter(component_md)
            component_id = frontmatter.get("id")
            realizes = frontmatter.get("realizes") or []
            for capability_id in realizes:
                capability_to_realizing.setdefault(capability_id, set()).add(component_id)

    scope = set(component_ids)
    return sorted(
        capability_id
        for capability_id, realizers in capability_to_realizing.items()
        if realizers & scope
    )


def check_readiness(
    repo_root: Path,
    changed_ids: list | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
) -> VerifyReport:
    repo_root = Path(repo_root)
    provenance_checker = _load_dependency(repo_root, "provenance-checker", "provenance_checker")

    if changed_ids:
        impact_analyzer = _load_dependency(repo_root, "impact-analyzer", "impact_analyzer")
        blast_report = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
        precondition_error = _get(blast_report, "precondition_error")
        if precondition_error is not None:
            raise ValueError(precondition_error)
        impacted = _get(blast_report, "impacted") or []
        component_ids = sorted({_get(entry, "component_id") for entry in impacted})
        scope = "blast-radius"
    else:
        component_ids = _discover_all_component_ids(repo_root)
        scope = "whole-corpus"

    components_result: dict = {}
    capabilities_result: dict = {}
    not_ready_reasons: list = []
    ready = True

    for component_id in component_ids:
        sealed_key = provenance_checker.current_sealed_key(component_id, repo_root)
        if sealed_key is not None:
            sealed_result = provenance_checker.check_sealed_provenance(component_id, repo_root)
            components_result[component_id] = sealed_result
            hit = _get(sealed_result, "hit")
            if not hit:
                ready = False
                reason = _get(sealed_result, "reason")
                not_ready_reasons.append(
                    f"{component_id}: sealed provenance {reason} — run hotdocs generate {component_id}"
                )
            continue

        key = provenance_checker.current_provenance_key(component_id, repo_root)
        spec_bundle_hash = _get(key, "spec_bundle_hash")
        gate_versions = _get(key, "gate_versions")
        check_result = provenance_checker.check_provenance(
            component_id, spec_bundle_hash, gate_versions, repo_root
        )
        components_result[component_id] = check_result
        hit = _get(check_result, "hit")

        if not hit:
            ready = False
            not_ready_reasons.append(
                f"{component_id}: no provenance for current spec state — run hotdocs generate {component_id}"
            )
            continue

        failed_checks = []
        failing_r_ids = []

        verification_report = _get(check_result, "verification_report")
        overall = _get(verification_report, "overall") if verification_report is not None else None
        if verification_report is None or overall != "pass":
            failed_checks.append("verification")
            requirement_results = _get(verification_report, "requirement_results", {}) or {}
            for r_id, status in requirement_results.items():
                if status == "fail":
                    failing_r_ids.append(r_id)

        license_scan = _get(check_result, "license_scan")
        if license_scan is not None and _get(license_scan, "blocked"):
            failed_checks.append("license_scan")

        secret_scan = _get(check_result, "secret_scan")
        if secret_scan is not None and _get(secret_scan, "flagged"):
            failed_checks.append("secret_scan")

        if failed_checks:
            ready = False
            message = f"{component_id}: {', '.join(failed_checks)} failing"
            if failing_r_ids:
                message += f" ({', '.join(sorted(failing_r_ids))})"
            not_ready_reasons.append(message)

    capability_ids = _capabilities_intersecting(repo_root, component_ids)
    if capability_ids:
        capability_scenario_verifier = _load_dependency(
            repo_root, "capability-scenario-verifier", "capability_scenario_verifier"
        )
        for capability_id in capability_ids:
            provenance_result = capability_scenario_verifier.check_capability_provenance(
                capability_id, repo_root
            )
            hit = _get(provenance_result, "hit")
            if hit:
                result = provenance_result
            else:
                if model is None:
                    raise ValueError(
                        f"capability {capability_id} needs a fresh run but no model was given"
                    )
                result = capability_scenario_verifier.run_capability_gates(
                    capability_id, repo_root, model, seed, llm_backend
                )

            capabilities_result[capability_id] = result

            report = _get(result, "capability_scenario_report")
            capability_entry = _get(report, capability_id) if report is not None else None
            capability_overall = _get(capability_entry, "overall") if capability_entry is not None else None
            if capability_overall != "pass":
                ready = False
                not_ready_reasons.append(f"{capability_id}: capability scenario verification failing")

    return VerifyReport(
        scope=scope,
        ready=ready,
        components=components_result,
        capabilities=capabilities_result,
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
    verification_plain = _to_plain(verification_report) if verification_report is not None else None

    record = {
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
    dest_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    return AttemptRecord(**record)


def last_requirement_failures(component_id: str, repo_root: Path) -> list:
    repo_root = Path(repo_root)
    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    if not attempts_dir.is_dir():
        return []

    files = sorted(attempts_dir.glob("*.json"))
    for path in reversed(files):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        verification = _get(data, "verification")
        if verification is not None:
            requirement_results = _get(verification, "requirement_results", {}) or {}
            return sorted(
                r_id for r_id, status in requirement_results.items() if status == "fail"
            )
    return []


def _verify_report_to_plain(report) -> dict:
    components = _get(report, "components") or {}
    capabilities = _get(report, "capabilities") or {}
    return {
        "scope": _get(report, "scope"),
        "ready": _get(report, "ready"),
        "components": {cid: _to_plain(result) for cid, result in components.items()},
        "capabilities": {cid: _to_plain(result) for cid, result in capabilities.items()},
        "not_ready_reasons": list(_get(report, "not_ready_reasons") or []),
    }


def _parse_known_flags(args, repeatable, known) -> tuple:
    positional = []
    flags: dict = {}
    i = 0
    n = len(args)
    while i < n:
        arg = args[i]
        if arg.startswith("--"):
            body = arg[2:]
            if "=" in body:
                name, value = body.split("=", 1)
            else:
                name = body
                i += 1
                if i >= n:
                    raise _UsageError(f"flag --{name} given last with no value")
                value = args[i]
            if name not in known:
                raise _UsageError(f"unknown argument: --{name}")
            if name in repeatable:
                flags.setdefault(name, []).append(value)
            else:
                flags[name] = value
            i += 1
        else:
            positional.append(arg)
            i += 1
    return positional, flags


def _main_verify(args) -> int:
    known_flags = {"changed", "model", "seed", "repo-root", "format"}
    positional, flags = _parse_known_flags(args, repeatable={"changed"}, known=known_flags)
    if positional:
        raise _UsageError(f"unknown argument: {positional[0]}")

    changed_ids = flags.get("changed") or None
    model = flags.get("model")

    seed_str = flags.get("seed", "0")
    try:
        seed = int(seed_str)
    except ValueError:
        raise _UsageError(f"invalid --seed: {seed_str}")

    repo_root = Path(flags.get("repo-root", "."))

    fmt = flags.get("format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")

    try:
        report = check_readiness(repo_root, changed_ids=changed_ids, model=model, seed=seed, llm_backend=None)
    except ValueError as exc:
        raise _UsageError(str(exc))

    ready = _get(report, "ready")

    if fmt == "json":
        print(json.dumps(_verify_report_to_plain(report), indent=2, sort_keys=True))
    else:
        print("ready" if ready else "not ready")
        for reason in (_get(report, "not_ready_reasons") or []):
            print(reason)

    return 0 if ready else 1


def _main_track_feedback(args) -> int:
    known_flags = {"repo-root"}
    positional, flags = _parse_known_flags(args, repeatable=set(), known=known_flags)
    if not positional:
        raise _UsageError("missing <component-id>")
    if len(positional) > 1:
        raise _UsageError(f"unknown argument: {positional[1]}")

    component_id = positional[0]
    repo_root = Path(flags.get("repo-root", "."))

    failures = last_requirement_failures(component_id, repo_root)
    print(",".join(failures))
    return 0


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        if not argv:
            raise _UsageError("missing subcommand")
        if argv[0] == "verify":
            return _main_verify(argv[1:])
        if argv[0] == "track" and len(argv) > 1 and argv[1] == "feedback":
            return _main_track_feedback(argv[2:])
        raise _UsageError(f"unknown subcommand: {argv[0]}")
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2