"""Provenance Tracker: `hotdocs verify` readiness checks and AttemptRecord history."""

from __future__ import annotations

import collections.abc
import dataclasses
import datetime
import enum
import importlib.util
import json
import math
import pathlib
import re
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# JSON conversion (specs/architecture/json-values.md)
# ---------------------------------------------------------------------------

def to_json(value):
    """Convert ``value`` into something ``json.dumps`` accepts."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, collections.abc.Mapping):
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
    if isinstance(value, pathlib.PurePath):
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


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class _Record(dict):
    """A dict whose keys are also readable as attributes."""

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
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if isinstance(obj, collections.abc.Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    here = Path(__file__).resolve().parent
    return next((d.parent for d in [here, *here.parents] if d.name == "gen"), here)


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


_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


def _frontmatter(path):
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    return (yaml.safe_load(match.group(1)) if match else None) or {}


def _component_frontmatters(repo_root):
    paths = sorted((Path(repo_root) / "specs" / "components").glob("*/component.md"))
    return [_frontmatter(p) for p in paths]


# ---------------------------------------------------------------------------
# check_readiness (R-TRACK-009/010/011/012/016)
# ---------------------------------------------------------------------------

def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    reasons = []
    components = {}
    capabilities = {}
    secret_scan = None

    if changed_ids:
        scope = "blast-radius"
        impact = _load("impact-analyzer", "impact_analyzer", repo_root)
        blast = impact.compute_blast_radius(changed_ids, repo_root)
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
        component_ids = [_get(entry, "component_id") for entry in _get(blast, "impacted")]
        frontmatters = None
    else:
        scope = "whole-corpus"
        frontmatters = _component_frontmatters(repo_root)
        component_ids = [fm["id"] for fm in frontmatters]

    if component_ids:
        checker = _load("provenance-checker", "provenance_checker", repo_root)

    for cid in component_ids:
        sealed_key = checker.current_sealed_key(cid, repo_root)
        if sealed_key is None:
            key = checker.current_provenance_key(cid, repo_root)
            result = checker.check_provenance(
                cid,
                _get(key, "spec_bundle_hash"),
                _get(key, "gate_versions"),
                repo_root,
            )
            components[cid] = result
            if not _get(result, "hit"):
                reasons.append(
                    f"{cid}: no provenance for current spec state — run hotdocs generate {cid}"
                )
                continue
            report = _get(result, "verification_report")
            if _get(report, "overall") != "pass":
                requirement_results = _get(report, "requirement_results") or {}
                failed = [rid for rid, v in requirement_results.items() if v == "fail"]
                reasons.append(f"{cid}: verification failed: {', '.join(failed)}")
            if _get(_get(result, "license_scan"), "blocked") is True:
                reasons.append(f"{cid}: license_scan blocked")
        else:
            result = checker.check_sealed_provenance(cid, repo_root)
            components[cid] = result
            if not _get(result, "hit"):
                reasons.append(
                    f"{cid}: sealed provenance {_get(result, 'reason')} — run hotdocs generate {cid}"
                )

    if frontmatters is None:
        frontmatters = _component_frontmatters(repo_root)
    in_scope = set(component_ids)
    capability_ids = sorted({
        cap
        for fm in frontmatters
        if fm.get("id") in in_scope
        for cap in (fm.get("realizes") or [])
    })

    if capability_ids:
        verifier = _load(
            "capability-scenario-verifier", "capability_scenario_verifier", repo_root
        )

    for cap in capability_ids:
        result = verifier.check_capability_provenance(cap, repo_root)
        if not _get(result, "hit"):
            if model is None:
                capabilities[cap] = result
                reasons.append(f"{cap}: needs a fresh run; pass --model")
                continue
            result = verifier.run_capability_gates(cap, repo_root, model, seed, llm_backend)
        capabilities[cap] = result
        entry = _get(_get(result, "capability_scenario_report"), cap)
        if _get(entry, "overall") != "pass":
            scenarios = _get(entry, "scenarios") or []
            if not scenarios:
                reasons.append(
                    f"{cap}: has no capability scenarios; add a CS- scenario to its file under specs/product/"
                )
            else:
                failed = [_get(s, "id") for s in scenarios if _get(s, "result") == "fail"]
                reasons.append(f"{cap}: capability scenarios failed: {', '.join(failed)}")

    if component_ids:
        try:
            scanner = _load("secret-scanner", "secret_scanner", repo_root)
            scan_result = scanner.scan(repo_root)
        except Exception as exc:  # reported, never raised (R-TRACK-016)
            reasons.append(f"secret_scan unavailable: {type(exc).__name__}: {exc}")
        else:
            to_dict = getattr(scan_result, "to_dict", None)
            secret_scan = to_dict() if callable(to_dict) else scan_result
            if _get(scan_result, "flagged"):
                matches = [
                    f"{_get(m, 'file')}:{_get(m, 'line')} {_get(m, 'rule_id')}"
                    for m in (_get(scan_result, "matches") or [])
                ]
                reasons.append(f"secret_scan flagged: {', '.join(matches)}")

    return VerifyReport(
        scope=scope,
        ready=not reasons,
        components=components,
        capabilities=capabilities,
        secret_scan=secret_scan,
        not_ready_reasons=reasons,
    )


# ---------------------------------------------------------------------------
# AttemptRecords (R-TRACK-004/007/008)
# ---------------------------------------------------------------------------

def _attempts_dir(component_id, repo_root):
    return Path(repo_root) / ".hotdocs" / "attempts" / component_id


def write_attempt_record(
    component_id, generation_result, verification_report, spec_bundle_hash, repo_root
):
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{now.microsecond:06d}"
    record = AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=to_json(generation_result),
        verification=to_json(verification_report),
    )
    directory = _attempts_dir(component_id, repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as fh:
        fh.write(json.dumps(record, indent=2))
    return record


def last_requirement_failures(component_id, repo_root):
    paths = sorted(_attempts_dir(component_id, repo_root).glob("*.json"), reverse=True)
    for path in paths:
        verification = json.loads(path.read_text(encoding="utf-8")).get("verification")
        if verification is None:
            continue
        criteria = verification.get("criteria") or []
        failures = []
        for rid, value in (verification.get("requirement_results") or {}).items():
            if value != "fail":
                continue
            non_passing = [
                c for c in criteria
                if c.get("covers") == rid and c.get("result") != "pass"
            ]
            if non_passing and all(
                c.get("failure_origin", "implementation") in ("test", "environment")
                for c in non_passing
            ):
                continue
            failures.append(rid)
        return sorted(failures)
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_VERIFY_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
_FEEDBACK_USAGE = "usage: hotdocs track feedback <component-id> [--repo-root=<dir>]"


class _UsageError(Exception):
    def __init__(self, cause, usage):
        super().__init__(cause)
        self.cause = cause
        self.usage = usage


def _parse(tokens, flags, usage):
    opts = {}
    positionals = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if tok.startswith("-"):
            name, eq, value = tok.partition("=")
            if name not in flags:
                raise _UsageError(f"unknown argument: {tok}", usage)
            if not eq:
                if i >= len(tokens):
                    raise _UsageError(f"{name} requires a value", usage)
                value = tokens[i]
                i += 1
            opts.setdefault(name, []).append(value)
        else:
            positionals.append(tok)
    return opts, positionals


def _verify(tokens):
    opts, positionals = _parse(
        tokens, {"--changed", "--model", "--seed", "--repo-root", "--format"}, _VERIFY_USAGE
    )
    if positionals:
        raise _UsageError(f"unknown argument: {positionals[0]}", _VERIFY_USAGE)
    seed_text = opts.get("--seed", ["0"])[-1]
    try:
        seed = int(seed_text)
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {seed_text}", _VERIFY_USAGE) from None
    fmt = opts.get("--format", ["text"])[-1]
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}", _VERIFY_USAGE)
    report = check_readiness(
        Path(opts.get("--repo-root", ["."])[-1]),
        changed_ids=opts.get("--changed") or None,
        model=opts.get("--model", [None])[-1],
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


def _feedback(tokens):
    opts, positionals = _parse(tokens, {"--repo-root"}, _FEEDBACK_USAGE)
    if not positionals:
        raise _UsageError("missing <component-id>", _FEEDBACK_USAGE)
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument: {positionals[1]}", _FEEDBACK_USAGE)
    failures = last_requirement_failures(
        positionals[0], Path(opts.get("--repo-root", ["."])[-1])
    )
    if failures:
        print(",".join(failures))
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    try:
        if argv[:1] == ["verify"]:
            return _verify(argv[1:])
        if argv[:2] == ["track", "feedback"]:
            return _feedback(argv[2:])
        cause = f"unknown command: {' '.join(argv[:2])}" if argv else "missing command"
        raise _UsageError(cause, f"{_VERIFY_USAGE}\n{_FEEDBACK_USAGE}")
    except _UsageError as err:
        print(f"usage error: {err.cause}", file=sys.stderr)
        print(err.usage, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
