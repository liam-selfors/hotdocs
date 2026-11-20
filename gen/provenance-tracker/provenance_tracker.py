"""Provenance tracker: `hotdocs verify` readiness checks and attempt history."""

import dataclasses
import datetime
import enum
import importlib.util
import json
import math
import re
import sys
from collections.abc import Mapping
from pathlib import Path, PurePath

import yaml

VERIFY_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
FEEDBACK_USAGE = "usage: hotdocs track feedback <component-id> [--repo-root=<dir>]"


# --------------------------------------------------------------------------
# JSON conversion (specs/architecture/json-values.md)
# --------------------------------------------------------------------------

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
        return sorted(items, key=lambda x: json.dumps(x, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_json(to_dict())
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


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _get(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


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


_FRONTMATTER = re.compile(r"---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.S)


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(_FRONTMATTER.match(text).group(1)) or {}


def _scan_components(repo_root):
    """Return [(component_id, realizes_list)] for every component.md, sorted by dir."""
    out = []
    for path in sorted((Path(repo_root) / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(path)
        out.append((fm.get("id"), fm.get("realizes") or []))
    return out


def _miss_reason(cid):
    return f"{cid}: no provenance for current spec state — run hotdocs generate {cid}"


# --------------------------------------------------------------------------
# check_readiness (R-TRACK-009 / 010 / 011 / 012)
# --------------------------------------------------------------------------

def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    pc = _load("provenance-checker", "provenance_checker", repo_root)
    corpus = _scan_components(repo_root)
    realizes = {cid: list(caps) for cid, caps in corpus}

    if changed_ids:
        scope_name = "blast-radius"
        ia = _load("impact-analyzer", "impact_analyzer", repo_root)
        report = ia.compute_blast_radius(list(changed_ids), repo_root)
        scope = [_get(entry, "component_id") for entry in (_get(report, "impacted") or [])]
    else:
        scope_name = "whole-corpus"
        scope = [cid for cid, _ in corpus]

    components = {}
    capabilities = {}
    reasons = []

    for cid in scope:
        sealed_key = pc.current_sealed_key(cid, repo_root)
        if sealed_key is None:
            key = pc.current_provenance_key(cid, repo_root)
            result = pc.check_provenance(
                cid, _get(key, "spec_bundle_hash"), _get(key, "gate_versions"), repo_root
            )
            components[cid] = result
            if not _get(result, "hit"):
                reasons.append(_miss_reason(cid))
                continue
            vr = _get(result, "verification_report")
            if _get(vr, "overall") != "pass":
                rr = _get(vr, "requirement_results") or {}
                fails = sorted(rid for rid, res in rr.items() if res == "fail")
                reasons.append(f"{cid}: verification failed ({', '.join(fails)})")
            if _get(_get(result, "license_scan"), "blocked"):
                reasons.append(f"{cid}: license_scan blocked")
            if _get(_get(result, "secret_scan"), "flagged"):
                reasons.append(f"{cid}: secret_scan flagged")
        else:
            result = pc.check_sealed_provenance(cid, repo_root)
            components[cid] = result
            if not _get(result, "hit"):
                reasons.append(
                    f"{cid}: sealed provenance {_get(result, 'reason')} — run hotdocs generate {cid}"
                )

    caps = sorted({cap for cid in scope for cap in realizes.get(cid, [])})
    if caps:
        csv = _load("capability-scenario-verifier", "capability_scenario_verifier", repo_root)
        for cap in caps:
            result = csv.check_capability_provenance(cap, repo_root)
            if not _get(result, "hit"):
                if model is None:
                    capabilities[cap] = result
                    reasons.append(f"{cap}: needs a fresh run; pass --model")
                    continue
                result = csv.run_capability_gates(cap, repo_root, model, seed, llm_backend)
            capabilities[cap] = result
            entry = _get(_get(result, "capability_scenario_report"), cap)
            if _get(entry, "overall") != "pass":
                reasons.append(f"{cap}: capability scenarios failed")

    return {
        "scope": scope_name,
        "ready": not reasons,
        "components": components,
        "capabilities": capabilities,
        "not_ready_reasons": reasons,
    }


# --------------------------------------------------------------------------
# Attempt records (R-TRACK-004 / 007 / 008)
# --------------------------------------------------------------------------

def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{now.microsecond:06x}"
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
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as fh:
        fh.write(json.dumps(record, indent=2))
    return record


def last_requirement_failures(component_id, repo_root):
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
            origins = [
                c.get("failure_origin", "implementation")
                for c in criteria
                if c.get("covers") == rid and c.get("result") != "pass"
            ]
            if origins and all(o in ("test", "environment") for o in origins):
                continue
            failures.append(rid)
        return sorted(failures)
    return []


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

class _UsageError(Exception):
    pass


def _parse(tokens, flags):
    values = {}
    positional = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        name, eq, val = tok.partition("=")
        if name in flags:
            if not eq:
                if i + 1 >= len(tokens):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                val = tokens[i]
            values.setdefault(name, []).append(val)
        elif tok.startswith("-"):
            raise _UsageError(f"unknown argument: {tok}")
        else:
            positional.append(tok)
        i += 1
    return values, positional


def _usage_error(cause, usage):
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _main_verify(tokens):
    try:
        values, positional = _parse(
            tokens, ("--changed", "--model", "--seed", "--repo-root", "--format")
        )
        if positional:
            raise _UsageError(f"unknown argument: {positional[0]}")
        seed_text = values.get("--seed", ["0"])[-1]
        try:
            seed = int(seed_text)
        except ValueError:
            raise _UsageError(f"--seed must be an integer: {seed_text}")
        fmt = values.get("--format", ["text"])[-1]
        if fmt not in ("json", "text"):
            raise _UsageError(f"invalid --format: {fmt}")
    except _UsageError as exc:
        return _usage_error(str(exc), VERIFY_USAGE)

    report = check_readiness(
        Path(values.get("--repo-root", ["."])[-1]),
        values.get("--changed") or None,
        values.get("--model", [None])[-1],
        seed,
    )
    ready = bool(_get(report, "ready"))
    if fmt == "json":
        print(json.dumps(to_json(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _main_feedback(tokens):
    try:
        values, positional = _parse(tokens, ("--repo-root",))
        if not positional:
            raise _UsageError("missing <component-id>")
        if len(positional) > 1:
            raise _UsageError(f"unknown argument: {positional[1]}")
    except _UsageError as exc:
        return _usage_error(str(exc), FEEDBACK_USAGE)

    failures = last_requirement_failures(
        positional[0], Path(values.get("--repo-root", ["."])[-1])
    )
    if failures:
        print(",".join(failures))
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:1] == ["verify"]:
        return _main_verify(argv[1:])
    if argv[:2] == ["track", "feedback"]:
        return _main_feedback(argv[2:])
    return _usage_error(
        "expected 'verify' or 'track feedback'", VERIFY_USAGE + "\n" + FEEDBACK_USAGE
    )
