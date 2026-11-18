"""provenance-tracker: readiness verdicts and attempt history (R-TRACK-004..012)."""

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


# --------------------------------------------------------------------------
# JSON conversion (specs/architecture/json-values.md)
# --------------------------------------------------------------------------

def _to_json(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, collections.abc.Mapping):
        return {
            (k if isinstance(k, str) else str(k)): _to_json(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_to_json(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_to_json(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, pathlib.PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return _to_json(value.value)
    if callable(getattr(value, "to_dict", None)):
        return _to_json(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _to_json(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            k: _to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _get(obj, key):
    if isinstance(obj, collections.abc.Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load(repo_root, slug, module_name):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name, pkg / "__init__.py",
            submodule_search_locations=[str(pkg)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_FRONTMATTER_RE = re.compile(r"---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.S)


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(_FRONTMATTER_RE.match(text).group(1)) or {}


def _component_frontmatters(repo_root):
    return [
        _frontmatter(path)
        for path in sorted(Path(repo_root).glob("specs/components/*/component.md"))
    ]


# --------------------------------------------------------------------------
# check_readiness (R-TRACK-009/010/011/012)
# --------------------------------------------------------------------------

def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    pc = _load(repo_root, "provenance-checker", "provenance_checker")
    frontmatters = _component_frontmatters(repo_root)

    if changed_ids:
        scope = "blast-radius"
        ia = _load(repo_root, "impact-analyzer", "impact_analyzer")
        blast = ia.compute_blast_radius(list(changed_ids), repo_root)
        component_ids = [_get(entry, "component_id") for entry in _get(blast, "impacted")]
    else:
        scope = "whole-corpus"
        component_ids = [fm.get("id") for fm in frontmatters]

    components = {}
    reasons = []

    for cid in component_ids:
        sealed_key = pc.current_sealed_key(cid, repo_root)
        if sealed_key is None:
            key = pc.current_provenance_key(cid, repo_root)
            result = pc.check_provenance(
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
                rr = _get(report, "requirement_results") or {}
                failing = [rid for rid, res in rr.items() if res == "fail"]
                reasons.append(f"{cid}: verification failed: {', '.join(failing)}")
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

    in_scope = set(component_ids)
    capability_ids = sorted({
        cap
        for fm in frontmatters
        if fm.get("id") in in_scope
        for cap in (fm.get("realizes") or [])
    })

    capabilities = {}
    if capability_ids:
        csv = _load(repo_root, "capability-scenario-verifier", "capability_scenario_verifier")
        for cap in capability_ids:
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
        "scope": scope,
        "ready": not reasons,
        "components": components,
        "capabilities": capabilities,
        "not_ready_reasons": reasons,
    }


# --------------------------------------------------------------------------
# Attempt history (R-TRACK-004/007/008)
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
        "generation": _to_json(generation_result),
        "verification": _to_json(verification_report),
    }
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    return record


def last_requirement_failures(component_id, repo_root):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    for path in sorted(directory.glob("*.json"), reverse=True):
        verification = json.loads(path.read_text(encoding="utf-8")).get("verification")
        if verification is not None:
            criteria = verification.get("criteria") or []
            failures = []
            for rid, res in verification["requirement_results"].items():
                if res != "fail":
                    continue
                non_pass = [
                    c for c in criteria
                    if c.get("covers") == rid and c.get("result") != "pass"
                ]
                if non_pass and all(
                    c.get("failure_origin", "implementation") == "test" for c in non_pass
                ):
                    continue
                failures.append(rid)
            return failures
    return []


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

class _UsageError(Exception):
    pass


def _parse(args, names):
    values = {}
    positionals = []
    i = 0
    while i < len(args):
        arg = args[i]
        name, eq, val = arg.partition("=")
        if name in names:
            if not eq:
                if i + 1 >= len(args):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                val = args[i]
            values.setdefault(name, []).append(val)
        elif arg.startswith("-"):
            raise _UsageError(f"unknown argument: {arg}")
        else:
            positionals.append(arg)
        i += 1
    return values, positionals


def _verify(args):
    values, positionals = _parse(
        args, {"--changed", "--model", "--seed", "--repo-root", "--format"}
    )
    if positionals:
        raise _UsageError(f"unknown argument: {positionals[0]}")
    seed_text = values.get("--seed", ["0"])[-1]
    try:
        seed = int(seed_text)
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {seed_text}")
    fmt = values.get("--format", ["text"])[-1]
    if fmt not in ("text", "json"):
        raise _UsageError(f"invalid --format: {fmt}")
    model = values.get("--model", [None])[-1]
    repo_root = Path(values.get("--repo-root", ["."])[-1])
    report = check_readiness(repo_root, values.get("--changed") or None, model, seed)
    ready = _get(report, "ready")
    if fmt == "json":
        print(json.dumps(_to_json(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons"):
            print(reason)
    return 0 if ready else 1


def _feedback(args):
    values, positionals = _parse(args, {"--repo-root"})
    if not positionals:
        raise _UsageError("missing <component-id>")
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument: {positionals[1]}")
    repo_root = Path(values.get("--repo-root", ["."])[-1])
    failures = last_requirement_failures(positionals[0], repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv):
    argv = list(argv)
    try:
        if argv[:1] == ["verify"]:
            return _verify(argv[1:])
        if argv[:2] == ["track", "feedback"]:
            return _feedback(argv[2:])
        raise _UsageError("expected 'verify' or 'track feedback'")
    except _UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
