"""Provenance tracker: `hotdocs verify` readiness checks and attempt history.

Answers "would a merge pass right now" by checking every in-scope
component's current provenance through `provenance-checker` (read-only,
never triggering generation) and checking-then-running every intersecting
capability through `capability-scenario-verifier`.  Also keeps a durable,
append-only, local history of `hotdocs generate` attempts.
"""

from __future__ import annotations

import dataclasses
import enum
import importlib.util
import json
import math
import secrets
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path, PurePath

import yaml


VERIFY_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
FEEDBACK_USAGE = "usage: hotdocs track feedback <component-id> [--repo-root=<dir>]"
GENERAL_USAGE = VERIFY_USAGE + "\n" + FEEDBACK_USAGE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def to_json(value):
    """Convert any value to plain JSON values (specs/architecture/json-values.md)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {
            (k if isinstance(k, str) else str(k)): to_json(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    if callable(getattr(value, "to_dict", None)):
        return to_json(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: to_json(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            k: to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_dependency(slug: str, module_name: str, repo_root: Path):
    """Load `<module_name>` from `<repo_root>/gen/<slug>/`, else the tool root's."""
    dep_dir = Path(repo_root) / "gen" / slug
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / slug
    flat = dep_dir / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg_dir = dep_dir / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    end = lines.index("---", 1)
    return yaml.safe_load("\n".join(lines[1:end])) or {}


def _scan_components(repo_root: Path) -> list[dict]:
    """Frontmatter of every specs/components/*/component.md, in directory order."""
    base = Path(repo_root) / "specs" / "components"
    return [
        _frontmatter(path)
        for path in sorted(base.glob("*/component.md"))
    ]


# ---------------------------------------------------------------------------
# check_readiness
# ---------------------------------------------------------------------------


def _check_component(pc, component_id: str, repo_root: Path, reasons: list):
    sealed_key = pc.current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        result = pc.check_sealed_provenance(component_id, repo_root)
        if not _get(result, "hit"):
            reasons.append(
                f"{component_id}: sealed provenance {_get(result, 'reason')} "
                f"— run hotdocs generate {component_id}"
            )
        return result

    key = pc.current_provenance_key(component_id, repo_root)
    result = pc.check_provenance(
        component_id,
        _get(key, "spec_bundle_hash"),
        _get(key, "gate_versions"),
        repo_root,
    )
    if not _get(result, "hit"):
        reasons.append(
            f"{component_id}: no provenance for current spec state "
            f"— run hotdocs generate {component_id}"
        )
        return result

    report = _get(result, "verification_report")
    if _get(report, "overall") != "pass":
        requirement_results = _get(report, "requirement_results") or {}
        failing = [rid for rid, verdict in requirement_results.items() if verdict == "fail"]
        reasons.append(f"{component_id}: verification failed: {', '.join(failing)}")
    if _get(_get(result, "license_scan"), "blocked"):
        reasons.append(f"{component_id}: license_scan blocked")
    if _get(_get(result, "secret_scan"), "flagged"):
        reasons.append(f"{component_id}: secret_scan flagged")
    return result


def check_readiness(
    repo_root: Path,
    changed_ids: list[str] | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
):
    """The live provenance query: would a merge pass right now."""
    repo_root = Path(repo_root)
    pc = _load_dependency("provenance-checker", "provenance_checker", repo_root)
    frontmatters = _scan_components(repo_root)

    if changed_ids:
        scope = "blast-radius"
        ia = _load_dependency("impact-analyzer", "impact_analyzer", repo_root)
        blast = ia.compute_blast_radius(list(changed_ids), repo_root)
        precondition_error = _get(blast, "precondition_error")
        if precondition_error is not None:
            return {
                "scope": scope,
                "ready": False,
                "components": {},
                "capabilities": {},
                "not_ready_reasons": [
                    f"blast radius unavailable: {precondition_error}"
                ],
            }
        component_ids = [
            _get(entry, "component_id") for entry in (_get(blast, "impacted") or [])
        ]
    else:
        scope = "whole-corpus"
        component_ids = [fm.get("id") for fm in frontmatters]

    reasons: list[str] = []
    components: dict = {}
    for component_id in component_ids:
        components[component_id] = _check_component(pc, component_id, repo_root, reasons)

    in_scope = set(component_ids)
    intersecting: set = set()
    for fm in frontmatters:
        if fm.get("id") in in_scope:
            intersecting.update(fm.get("realizes") or [])

    capabilities: dict = {}
    if intersecting:
        csv = _load_dependency(
            "capability-scenario-verifier", "capability_scenario_verifier", repo_root
        )
        for capability_id in sorted(intersecting):
            result = csv.check_capability_provenance(capability_id, repo_root)
            if not _get(result, "hit"):
                if model is None:
                    capabilities[capability_id] = result
                    reasons.append(f"{capability_id}: needs a fresh run; pass --model")
                    continue
                result = csv.run_capability_gates(
                    capability_id, repo_root, model, seed, llm_backend
                )
            capabilities[capability_id] = result
            entry = _get(_get(result, "capability_scenario_report"), capability_id)
            if _get(entry, "overall") != "pass":
                reasons.append(f"{capability_id}: capability scenarios failed")

    return {
        "scope": scope,
        "ready": not reasons,
        "components": components,
        "capabilities": capabilities,
        "not_ready_reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Attempt history
# ---------------------------------------------------------------------------


def _attempts_dir(component_id: str, repo_root: Path) -> Path:
    return Path(repo_root) / ".hotdocs" / "attempts" / component_id


def write_attempt_record(
    component_id: str,
    generation_result,
    verification_report,
    spec_bundle_hash: str,
    repo_root: Path,
):
    """Write one append-only AttemptRecord and return it in its written form."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{secrets.token_hex(3)}"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": timestamp,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": to_json(generation_result),
        "verification": to_json(verification_report),
    }
    directory = _attempts_dir(component_id, repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    return record


def _is_feedback(rid: str, criteria: list) -> bool:
    failing = [
        c for c in criteria
        if c.get("covers") == rid and c.get("result") != "pass"
    ]
    return not failing or any(
        c.get("failure_origin", "implementation") not in ("test", "environment")
        for c in failing
    )


def last_requirement_failures(component_id: str, repo_root: Path) -> list[str]:
    """Failing R-ids from the most recent attempt with a non-null verification."""
    directory = _attempts_dir(component_id, repo_root)
    paths = sorted(
        directory.glob("*.json"),
        key=lambda p: (p.name[:20], p.stat().st_mtime_ns, p.name),
    )
    verification = None
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("verification") is not None:
            verification = record["verification"]
    if verification is None:
        return []
    criteria = verification.get("criteria") or []
    requirement_results = verification.get("requirement_results") or {}
    return sorted(
        rid
        for rid, verdict in requirement_results.items()
        if verdict == "fail" and _is_feedback(rid, criteria)
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse(tokens: list[str], value_flags: set[str]):
    """Parse `--flag=value` / `--flag value` tokens; return (flags, positionals)."""
    flags: dict[str, list[str]] = {}
    positionals: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, eq, value = token.partition("=")
        if name in value_flags:
            if not eq:
                if i + 1 >= len(tokens):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                value = tokens[i]
            flags.setdefault(name, []).append(value)
        elif token.startswith("-"):
            raise _UsageError(f"unknown argument: {token}")
        else:
            positionals.append(token)
        i += 1
    return flags, positionals


def _usage_error(cause: str, usage: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _run_verify(tokens: list[str]) -> int:
    try:
        flags, positionals = _parse(
            tokens, {"--changed", "--model", "--seed", "--repo-root", "--format"}
        )
        if positionals:
            raise _UsageError(f"unknown argument: {positionals[0]}")
        try:
            seed = int(flags.get("--seed", ["0"])[-1])
        except ValueError:
            raise _UsageError("--seed must be an integer")
        fmt = flags.get("--format", ["text"])[-1]
        if fmt not in ("json", "text"):
            raise _UsageError(f"invalid --format: {fmt}")
    except _UsageError as exc:
        return _usage_error(str(exc), VERIFY_USAGE)

    repo_root = Path(flags["--repo-root"][-1]) if "--repo-root" in flags else Path.cwd()
    report = check_readiness(
        repo_root,
        changed_ids=flags.get("--changed") or None,
        model=flags.get("--model", [None])[-1],
        seed=seed,
    )
    ready = bool(_get(report, "ready"))
    if fmt == "json":
        print(json.dumps(to_json(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _run_feedback(tokens: list[str]) -> int:
    try:
        flags, positionals = _parse(tokens, {"--repo-root"})
        if not positionals:
            raise _UsageError("missing <component-id>")
        if len(positionals) > 1:
            raise _UsageError(f"unknown argument: {positionals[1]}")
    except _UsageError as exc:
        return _usage_error(str(exc), FEEDBACK_USAGE)

    repo_root = Path(flags["--repo-root"][-1]) if "--repo-root" in flags else Path.cwd()
    failures = last_requirement_failures(positionals[0], repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:1] == ["verify"]:
        return _run_verify(argv[1:])
    if argv[:2] == ["track", "feedback"]:
        return _run_feedback(argv[2:])
    cause = f"unknown command: {' '.join(argv[:2])}" if argv else "missing command"
    return _usage_error(cause, GENERAL_USAGE)


if __name__ == "__main__":
    sys.exit(main())
