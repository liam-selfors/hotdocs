"""Provenance tracker: `hotdocs verify` readiness checks and attempt history."""

import dataclasses
import enum
import importlib.util
import json
import math
import pathlib
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import yaml


class _Record(dict):
    """A plain dict that also exposes its keys as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


class VerifyReport(_Record):
    """`interface/data/VerifyReport.md`."""


class AttemptRecord(_Record):
    """`interface/data/AttemptRecord.md`."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def to_json(value):
    """Convert `value` to plain JSON values (`specs/architecture/json-values.md`)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {
            (k if isinstance(k, str) else str(k)): to_json(v) for k, v in value.items()
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
        return {
            f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            k: to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load(repo_root, slug):
    module_name = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module_name}.py"
    search = None
    if not path.is_file():
        path = directory / module_name / "__init__.py"
        search = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=search
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return yaml.safe_load("\n".join(lines[1:i])) or {}
    return {}


def _corpus(repo_root):
    """Every component as (id, realizes list), in directory order."""
    entries = []
    for path in sorted((Path(repo_root) / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(path)
        realizes = fm.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        entries.append((fm.get("id"), list(realizes)))
    return entries


# ---------------------------------------------------------------------------
# check_readiness
# ---------------------------------------------------------------------------


def _check_component(pc, cid, repo_root, reasons):
    sealed_key = pc.current_sealed_key(cid, repo_root)
    if sealed_key is not None:
        result = pc.check_sealed_provenance(cid, repo_root)
        if not _get(result, "hit"):
            reasons.append(
                f"{cid}: sealed provenance {_get(result, 'reason')}"
                f" — run hotdocs generate {cid}"
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
        fails = sorted(k for k, v in rr.items() if v == "fail")
        reasons.append(f"{cid}: verification failed: {', '.join(fails)}")
    if _get(_get(result, "license_scan"), "blocked"):
        reasons.append(f"{cid}: license_scan blocked")
    if _get(_get(result, "secret_scan"), "flagged"):
        reasons.append(f"{cid}: secret_scan flagged")
    return result


def _capability_passes(cap, result):
    report = _get(result, "capability_scenario_report")
    return _get(_get(report, cap), "overall") == "pass"


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    pc = _load(repo_root, "provenance-checker")
    reasons = []
    corpus = _corpus(repo_root)

    if changed_ids:
        scope = "blast-radius"
        ia = _load(repo_root, "impact-analyzer")
        blast = ia.compute_blast_radius(list(changed_ids), repo_root)
        error = _get(blast, "precondition_error")
        if error is not None:
            return VerifyReport(
                scope=scope,
                ready=False,
                components={},
                capabilities={},
                not_ready_reasons=[f"blast radius unavailable: {error}"],
            )
        ids = [_get(entry, "component_id") for entry in _get(blast, "impacted")]
    else:
        scope = "whole-corpus"
        ids = [cid for cid, _ in corpus if cid is not None]

    components = {}
    for cid in ids:
        components[cid] = _check_component(pc, cid, repo_root, reasons)

    in_scope = set(ids)
    realizers = {}
    for cid, realizes in corpus:
        for cap in realizes:
            realizers.setdefault(cap, set()).add(cid)
    caps = sorted(cap for cap, comps in realizers.items() if comps & in_scope)

    capabilities = {}
    if caps:
        csv = _load(repo_root, "capability-scenario-verifier")
        for cap in caps:
            result = csv.check_capability_provenance(cap, repo_root)
            if not _get(result, "hit"):
                if model is None:
                    capabilities[cap] = result
                    reasons.append(f"{cap}: needs a fresh run; pass --model")
                    continue
                result = csv.run_capability_gates(cap, repo_root, model, seed, llm_backend)
            capabilities[cap] = result
            if not _capability_passes(cap, result):
                reasons.append(f"{cap}: capability scenarios failed")

    return VerifyReport(
        scope=scope,
        ready=not reasons,
        components=components,
        capabilities=capabilities,
        not_ready_reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Attempt history
# ---------------------------------------------------------------------------


def _attempts_dir(repo_root, component_id):
    return Path(repo_root) / ".hotdocs" / "attempts" / component_id


def write_attempt_record(
    component_id, generation_result, verification_report, spec_bundle_hash, repo_root
):
    directory = _attempts_dir(repo_root, component_id)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = len(list(directory.glob("*.json")))
    attempt_id = f"{timestamp}-{count:06x}"
    record = AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=to_json(generation_result),
        verification=to_json(verification_report),
    )
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=2))
    return record


def _feedback_ids(verification):
    rr = verification.get("requirement_results") or {}
    criteria = verification.get("criteria") or []
    out = []
    for rid, result in rr.items():
        if result != "fail":
            continue
        origins = [
            c.get("failure_origin", "implementation")
            for c in criteria
            if c.get("covers") == rid and c.get("result") != "pass"
        ]
        if origins and all(o in ("test", "environment") for o in origins):
            continue
        out.append(rid)
    return sorted(out)


def last_requirement_failures(component_id, repo_root):
    directory = _attempts_dir(repo_root, component_id)
    for path in sorted(directory.glob("*.json"), reverse=True):
        record = json.loads(path.read_text(encoding="utf-8"))
        verification = record.get("verification")
        if verification is not None:
            return _feedback_ids(verification)
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_VERIFY_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
_FEEDBACK_USAGE = "usage: hotdocs track feedback <component-id> [--repo-root=<dir>]"
_MAIN_USAGE = f"{_VERIFY_USAGE}\n{_FEEDBACK_USAGE}"


class _UsageError(Exception):
    pass


def _usage(cause, usage):
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _parse(tokens, flags):
    values = {}
    positionals = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        name, eq, val = tok.partition("=")
        if name in flags:
            if not eq:
                if i + 1 >= len(tokens):
                    raise _UsageError(f"{tok} requires a value")
                i += 1
                val = tokens[i]
            values.setdefault(name, []).append(val)
        elif tok.startswith("-"):
            raise _UsageError(f"unknown argument: {tok}")
        else:
            positionals.append(tok)
        i += 1
    return values, positionals


def _verify(tokens):
    try:
        values, positionals = _parse(
            tokens, ("--changed", "--model", "--seed", "--repo-root", "--format")
        )
        if positionals:
            raise _UsageError(f"unknown argument: {positionals[0]}")
        try:
            seed = int(values.get("--seed", ["0"])[-1])
        except ValueError:
            raise _UsageError(f"--seed must be an integer: {values['--seed'][-1]}") from None
        fmt = values.get("--format", ["text"])[-1]
        if fmt not in ("json", "text"):
            raise _UsageError(f"invalid --format: {fmt}")
    except _UsageError as exc:
        return _usage(exc, _VERIFY_USAGE)
    repo_root = Path(values.get("--repo-root", ["."])[-1])
    model = values.get("--model", [None])[-1]
    changed = values.get("--changed") or None
    report = check_readiness(repo_root, changed, model, seed)
    ready = bool(_get(report, "ready"))
    if fmt == "json":
        print(json.dumps(to_json(report)))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _feedback(tokens):
    try:
        values, positionals = _parse(tokens, ("--repo-root",))
        if not positionals:
            raise _UsageError("missing <component-id>")
        if len(positionals) > 1:
            raise _UsageError(f"unknown argument: {positionals[1]}")
    except _UsageError as exc:
        return _usage(exc, _FEEDBACK_USAGE)
    repo_root = Path(values.get("--repo-root", ["."])[-1])
    failures = last_requirement_failures(positionals[0], repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:1] == ["verify"]:
        return _verify(argv[1:])
    if argv[:2] == ["track", "feedback"]:
        return _feedback(argv[2:])
    return _usage(f"unknown command: {' '.join(argv[:2])}", _MAIN_USAGE)
