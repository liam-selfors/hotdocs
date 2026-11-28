"""Provenance Tracker: `hotdocs verify` readiness and attempt-record history."""

from __future__ import annotations

import dataclasses
import enum
import importlib.util
import json
import math
import pathlib
import re
import secrets
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import yaml

VERIFY_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
FEEDBACK_USAGE = "usage: hotdocs track feedback <component-id> [--repo-root=<dir>]"
ALL_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text] | "
    "hotdocs track feedback <component-id> [--repo-root=<dir>]"
)


# ---------------------------------------------------------------------------
# JSON conversion (specs/architecture/json-values.md)
# ---------------------------------------------------------------------------

def to_json(value):
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
        return [to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(v) for v in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, pathlib.PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    if callable(getattr(value, "to_dict", None)):
        return to_json(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if hasattr(value, "__dict__"):
        return {
            k: to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load(slug: str, module_name: str, repo_root) -> object:
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    flat = directory / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        init = directory / module_name / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            module_name, init, submodule_search_locations=[str(init.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|\Z)", re.S)


def _frontmatter(path: Path) -> dict:
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if match is None:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def _component_files(root: Path) -> list[Path]:
    return sorted((root / "specs" / "components").glob("*/component.md"))


# ---------------------------------------------------------------------------
# check_readiness (R-TRACK-009/010/011/012/016)
# ---------------------------------------------------------------------------

def check_readiness(
    repo_root: Path,
    changed_ids: list[str] | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
):
    root = Path(repo_root)
    checker = _load("provenance-checker", "provenance_checker", repo_root)
    scope = "blast-radius" if changed_ids else "whole-corpus"
    components: dict = {}
    capabilities: dict = {}
    reasons: list[str] = []
    secret_scan = None

    if changed_ids:
        analyzer = _load("impact-analyzer", "impact_analyzer", repo_root)
        radius = analyzer.compute_blast_radius(list(changed_ids), repo_root)
        error = _get(radius, "precondition_error")
        if error is not None:
            return {
                "scope": scope,
                "ready": False,
                "components": {},
                "capabilities": {},
                "secret_scan": None,
                "not_ready_reasons": [f"blast radius unavailable: {error}"],
            }
        ids = [_get(entry, "component_id") for entry in _get(radius, "impacted")]
    else:
        ids = []
        for path in _component_files(root):
            ids.append(_frontmatter(path).get("id"))

    for cid in ids:
        sealed_key = checker.current_sealed_key(cid, repo_root)
        if sealed_key is None:
            key = checker.current_provenance_key(cid, repo_root)
            result = checker.check_provenance(
                cid, _get(key, "spec_bundle_hash"), _get(key, "gate_versions"), repo_root
            )
            components[cid] = result
            if not _get(result, "hit"):
                reasons.append(
                    f"{cid}: no provenance for current spec state — run hotdocs generate {cid}"
                )
                continue
            report = _get(result, "verification_report")
            if _get(report, "overall") != "pass":
                failed = [
                    rid
                    for rid, res in (_get(report, "requirement_results") or {}).items()
                    if res == "fail"
                ]
                reasons.append(f"{cid}: verification failed: {', '.join(failed)}")
            if _get(_get(result, "license_scan"), "blocked") is True:
                reasons.append(f"{cid}: license_scan blocked")
        else:
            result = checker.check_sealed_provenance(cid, repo_root)
            components[cid] = result
            if not _get(result, "hit"):
                reasons.append(
                    f"{cid}: sealed provenance {_get(result, 'reason')} — "
                    f"run hotdocs generate {cid}"
                )

    scope_set = set(ids)
    realized: set = set()
    for path in _component_files(root):
        fm = _frontmatter(path)
        if fm.get("id") not in scope_set:
            continue
        realizes = fm.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        realized.update(realizes)

    if realized:
        verifier = _load(
            "capability-scenario-verifier", "capability_scenario_verifier", repo_root
        )
        for cap in sorted(realized):
            result = verifier.check_capability_provenance(cap, repo_root)
            if not _get(result, "hit"):
                if model is None:
                    capabilities[cap] = result
                    reasons.append(f"{cap}: needs a fresh run; pass --model")
                    continue
                result = verifier.run_capability_gates(
                    cap, repo_root, model, seed, llm_backend
                )
            capabilities[cap] = result
            entry = _get(_get(result, "capability_scenario_report"), cap)
            if _get(entry, "overall") != "pass":
                scenarios = _get(entry, "scenarios") or []
                if not scenarios:
                    reasons.append(
                        f"{cap}: has no capability scenarios; add a CS- scenario to "
                        f"its file under specs/product/"
                    )
                else:
                    failed = [
                        _get(s, "id") for s in scenarios if _get(s, "result") == "fail"
                    ]
                    reasons.append(
                        f"{cap}: capability scenarios failed: {', '.join(failed)}"
                    )

    if ids:
        try:
            scanner = _load("secret-scanner", "secret_scanner", repo_root)
            scanned = scanner.scan(repo_root)
            to_dict = getattr(scanned, "to_dict", None)
            secret_scan = to_dict() if callable(to_dict) else scanned
            if _get(scanned, "flagged"):
                matches = [
                    f"{_get(m, 'file')}:{_get(m, 'line')} {_get(m, 'rule_id')}"
                    for m in (_get(scanned, "matches") or [])
                ]
                reasons.append(f"secret_scan flagged: {', '.join(matches)}")
        except Exception as exc:  # noqa: BLE001 - never raised to the caller
            secret_scan = None
            reasons.append(f"secret_scan unavailable: {type(exc).__name__}: {exc}")

    return {
        "scope": scope,
        "ready": not reasons,
        "components": components,
        "capabilities": capabilities,
        "secret_scan": secret_scan,
        "not_ready_reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Attempt records (R-TRACK-004/007/008)
# ---------------------------------------------------------------------------

def write_attempt_record(
    component_id: str,
    generation_result,
    verification_report,
    spec_bundle_hash: str,
    repo_root: Path,
):
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{now.microsecond:06d}-{secrets.token_hex(3)}"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": timestamp,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": to_json(generation_result),
        "verification": to_json(verification_report),
    }
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=2))
    return record


def last_requirement_failures(component_id: str, repo_root: Path) -> list[str]:
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    for path in sorted(directory.glob("*.json"), reverse=True):
        record = json.loads(path.read_text(encoding="utf-8"))
        verification = record.get("verification")
        if verification is None:
            continue
        criteria = verification.get("criteria") or []
        failures = []
        for rid, res in (verification.get("requirement_results") or {}).items():
            if res != "fail":
                continue
            not_passing = [
                c for c in criteria
                if c.get("covers") == rid and c.get("result") != "pass"
            ]
            if not_passing and all(
                c.get("failure_origin", "implementation") in ("test", "environment")
                for c in not_passing
            ):
                continue
            failures.append(rid)
        return failures
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _UsageError(Exception):
    pass


def _usage(cause: str, usage: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _parse(args: list[str], value_flags: tuple, positional_limit: int):
    values: dict = {}
    positionals: list[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        name, eq, value = token.partition("=")
        if name in value_flags:
            if not eq:
                if i + 1 >= len(args):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                value = args[i]
            values.setdefault(name, []).append(value)
        elif not token.startswith("-") and len(positionals) < positional_limit:
            positionals.append(token)
        else:
            raise _UsageError(f"unknown argument: {token}")
        i += 1
    return values, positionals


def _main_verify(args: list[str]) -> int:
    try:
        values, _ = _parse(
            args, ("--changed", "--model", "--seed", "--repo-root", "--format"), 0
        )
        seed_text = values.get("--seed", ["0"])[-1]
        try:
            seed = int(seed_text)
        except ValueError:
            raise _UsageError(f"--seed must be an integer: {seed_text}")
        fmt = values.get("--format", ["text"])[-1]
        if fmt not in ("json", "text"):
            raise _UsageError(f"invalid --format: {fmt}")
    except _UsageError as exc:
        return _usage(str(exc), VERIFY_USAGE)
    repo_root = Path(values["--repo-root"][-1]) if "--repo-root" in values else Path.cwd()
    model = values.get("--model", [None])[-1]
    changed = values.get("--changed") or None
    report = check_readiness(repo_root, changed, model, seed)
    ready = bool(_get(report, "ready"))
    if fmt == "json":
        print(json.dumps(to_json(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _main_feedback(args: list[str]) -> int:
    try:
        values, positionals = _parse(args, ("--repo-root",), 1)
        if not positionals:
            raise _UsageError("missing <component-id>")
    except _UsageError as exc:
        return _usage(str(exc), FEEDBACK_USAGE)
    repo_root = Path(values["--repo-root"][-1]) if "--repo-root" in values else Path.cwd()
    failures = last_requirement_failures(positionals[0], repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["verify"]:
        return _main_verify(args[1:])
    if args[:2] == ["track", "feedback"]:
        return _main_feedback(args[2:])
    return _usage(
        f"unknown command: {' '.join(args[:2]) if args else '(none)'}", ALL_USAGE
    )
