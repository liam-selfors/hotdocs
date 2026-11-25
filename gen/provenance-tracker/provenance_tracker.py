"""provenance-tracker: `hotdocs verify` readiness checks and AttemptRecord history."""

from __future__ import annotations

import dataclasses
import enum
import importlib.util
import json
import math
import re
import sys
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path, PurePath

import yaml


VERIFY_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
FEEDBACK_USAGE = "usage: hotdocs track feedback <component-id> [--repo-root=<dir>]"
GENERAL_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text] | "
    "hotdocs track feedback <component-id> [--repo-root=<dir>]"
)

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)

_last_ns = 0


class _Record(dict):
    """A plain dict whose keys are also readable as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


class VerifyReport(_Record):
    pass


class AttemptRecord(_Record):
    pass


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_json(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {
            (k if isinstance(k, str) else str(k)): _to_json(v) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_to_json(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_to_json(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return _to_json(value.value)
    if callable(getattr(value, "to_dict", None)):
        return _to_json(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _to_json(getattr(value, f.name)) for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            k: _to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_dependency(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module_name}.py"
    if not path.is_file():
        path = base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(path):
    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if match is None:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def _component_frontmatters(repo_root):
    files = sorted((Path(repo_root) / "specs" / "components").glob("*/component.md"))
    return [_frontmatter(f) for f in files]


# ---------------------------------------------------------------------------
# check_readiness
# ---------------------------------------------------------------------------


def _check_component(pc, cid, repo_root, reasons):
    sealed_key = pc.current_sealed_key(cid, repo_root)
    if sealed_key is not None:
        result = pc.check_sealed_provenance(cid, repo_root)
        if not _get(result, "hit"):
            reasons.append(
                f"{cid}: sealed provenance {_get(result, 'reason')} — run hotdocs generate {cid}"
            )
        return result

    key = pc.current_provenance_key(cid, repo_root)
    result = pc.check_provenance(
        cid, _get(key, "spec_bundle_hash"), _get(key, "gate_versions"), repo_root
    )
    if not _get(result, "hit"):
        reasons.append(
            f"{cid}: no provenance for current spec state — run hotdocs generate {cid}"
        )
        return result

    report = _get(result, "verification_report")
    if _get(report, "overall") != "pass":
        rr = _get(report, "requirement_results") or {}
        failing = sorted(rid for rid, res in rr.items() if res == "fail")
        entry = f"{cid}: verification failed"
        if failing:
            entry += ": " + ", ".join(failing)
        reasons.append(entry)

    license_scan = _get(result, "license_scan")
    if _get(license_scan, "blocked") is True:
        reasons.append(f"{cid}: license_scan blocked")
    return result


def _capability_reason(cap_id, result):
    report = _get(_get(result, "capability_scenario_report"), cap_id)
    if _get(report, "overall") == "pass":
        return None
    scenarios = _get(report, "scenarios") or []
    if not scenarios:
        return (
            f"{cap_id}: has no capability scenarios; "
            "add a CS- scenario to its file under specs/product/"
        )
    failed = [_get(s, "id") for s in scenarios if _get(s, "result") == "fail"]
    return f"{cap_id}: capability scenarios failed: " + ", ".join(str(i) for i in failed)


def check_readiness(
    repo_root: Path,
    changed_ids: list[str] | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
) -> VerifyReport:
    repo_root = Path(repo_root)
    reasons: list[str] = []
    components: dict = {}
    capabilities: dict = {}

    if changed_ids:
        scope = "blast-radius"
        impact_analyzer = _load_dependency("impact-analyzer", "impact_analyzer", repo_root)
        blast = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
        precondition_error = _get(blast, "precondition_error")
        if precondition_error is not None:
            return VerifyReport(
                scope=scope,
                ready=False,
                components={},
                capabilities={},
                secret_scan=None,
                not_ready_reasons=[f"blast radius unavailable: {precondition_error}"],
            )
        component_ids = [_get(e, "component_id") for e in (_get(blast, "impacted") or [])]
        frontmatters = _component_frontmatters(repo_root)
    else:
        scope = "whole-corpus"
        frontmatters = _component_frontmatters(repo_root)
        component_ids = [fm.get("id") for fm in frontmatters if fm.get("id")]

    pc = _load_dependency("provenance-checker", "provenance_checker", repo_root)
    for cid in component_ids:
        components[cid] = _check_component(pc, cid, repo_root, reasons)

    in_scope = set(component_ids)
    cap_ids = sorted(
        {
            cap
            for fm in frontmatters
            if fm.get("id") in in_scope
            for cap in (fm.get("realizes") or [])
        }
    )
    if cap_ids:
        csv = _load_dependency(
            "capability-scenario-verifier", "capability_scenario_verifier", repo_root
        )
        for cap_id in cap_ids:
            result = csv.check_capability_provenance(cap_id, repo_root)
            if not _get(result, "hit"):
                if model is None:
                    capabilities[cap_id] = result
                    reasons.append(f"{cap_id}: needs a fresh run; pass --model")
                    continue
                result = csv.run_capability_gates(cap_id, repo_root, model, seed, llm_backend)
            capabilities[cap_id] = result
            reason = _capability_reason(cap_id, result)
            if reason is not None:
                reasons.append(reason)

    secret_scan = None
    if component_ids:
        try:
            scanner = _load_dependency("secret-scanner", "secret_scanner", repo_root)
            scan_result = scanner.scan(repo_root)
        except Exception as exc:  # noqa: BLE001 - reported, never raised
            reasons.append(f"secret_scan unavailable: {type(exc).__name__}: {exc}")
        else:
            to_dict = getattr(scan_result, "to_dict", None)
            secret_scan = to_dict() if callable(to_dict) else scan_result
            if _get(scan_result, "flagged"):
                matches = _get(scan_result, "matches") or []
                reasons.append(
                    "secret_scan flagged: "
                    + ", ".join(
                        f"{_get(m, 'file')}:{_get(m, 'line')} {_get(m, 'rule_id')}"
                        for m in matches
                    )
                )

    return VerifyReport(
        scope=scope,
        ready=not reasons,
        components=components,
        capabilities=capabilities,
        secret_scan=secret_scan,
        not_ready_reasons=reasons,
    )


# ---------------------------------------------------------------------------
# AttemptRecord history
# ---------------------------------------------------------------------------


def write_attempt_record(
    component_id: str,
    generation_result,
    verification_report,
    spec_bundle_hash: str,
    repo_root: Path,
) -> AttemptRecord:
    global _last_ns
    ns = max(time.time_ns(), _last_ns + 1000)
    _last_ns = ns
    now = datetime.fromtimestamp(ns // 1_000_000_000, tz=timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    micros = (ns // 1000) % 1_000_000
    attempt_id = f"{timestamp}-{micros:06x}"

    record = AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=_to_json(generation_result),
        verification=_to_json(verification_report),
    )
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{attempt_id}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    return record


def _feedback_ids(verification):
    requirement_results = verification.get("requirement_results") or {}
    criteria = verification.get("criteria") or []
    failing = []
    for rid, res in requirement_results.items():
        if res != "fail":
            continue
        non_pass = [
            c for c in criteria if c.get("covers") == rid and c.get("result") != "pass"
        ]
        if non_pass and all(
            c.get("failure_origin", "implementation") in ("test", "environment")
            for c in non_pass
        ):
            continue
        failing.append(rid)
    return sorted(failing)


def last_requirement_failures(component_id: str, repo_root: Path) -> list[str]:
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    for path in sorted(directory.glob("*.json"), reverse=True):
        record = json.loads(path.read_text(encoding="utf-8"))
        verification = record.get("verification")
        if verification is not None:
            return _feedback_ids(verification)
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _usage_error(cause, usage):
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _parse(tokens, flags):
    values: dict = {}
    positionals = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            name, eq, val = tok.partition("=")
            if name not in flags:
                return None, None, f"unknown argument: {tok}"
            if not eq:
                if i + 1 >= len(tokens):
                    return None, None, f"{name} requires a value"
                i += 1
                val = tokens[i]
            values.setdefault(name, []).append(val)
        else:
            positionals.append(tok)
        i += 1
    return values, positionals, None


def _main_verify(tokens):
    values, positionals, error = _parse(
        tokens, ("--changed", "--model", "--seed", "--repo-root", "--format")
    )
    if error is not None:
        return _usage_error(error, VERIFY_USAGE)
    if positionals:
        return _usage_error(f"unknown argument: {positionals[0]}", VERIFY_USAGE)
    seed_text = values.get("--seed", ["0"])[-1]
    try:
        seed = int(seed_text)
    except ValueError:
        return _usage_error(f"--seed must be an integer: {seed_text}", VERIFY_USAGE)
    fmt = values.get("--format", ["text"])[-1]
    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format: {fmt}", VERIFY_USAGE)
    repo_root = Path(values["--repo-root"][-1]) if "--repo-root" in values else Path.cwd()
    model = values.get("--model", [None])[-1]
    changed = values.get("--changed") or None

    report = check_readiness(repo_root, changed, model, seed)
    ready = bool(_get(report, "ready"))
    if fmt == "json":
        print(json.dumps(_to_json(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _main_feedback(tokens):
    values, positionals, error = _parse(tokens, ("--repo-root",))
    if error is not None:
        return _usage_error(error, FEEDBACK_USAGE)
    if not positionals:
        return _usage_error("missing <component-id>", FEEDBACK_USAGE)
    if len(positionals) > 1:
        return _usage_error(f"unknown argument: {positionals[1]}", FEEDBACK_USAGE)
    repo_root = Path(values["--repo-root"][-1]) if "--repo-root" in values else Path.cwd()
    ids = last_requirement_failures(positionals[0], repo_root)
    if ids:
        print(",".join(ids))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:1] == ["verify"]:
        return _main_verify(argv[1:])
    if argv[:2] == ["track", "feedback"]:
        return _main_feedback(argv[2:])
    cause = f"unknown command: {' '.join(argv[:2])}" if argv else "missing command"
    return _usage_error(cause, GENERAL_USAGE)
