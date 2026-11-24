"""provenance-tracker: readiness checks (`hotdocs verify`) and attempt history."""

import dataclasses
import enum
import importlib.util
import json
import math
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


class _Record(dict):
    """A plain dict whose keys are also readable as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class VerifyReport(_Record):
    pass


class AttemptRecord(_Record):
    pass


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
        return sorted(items, key=lambda i: json.dumps(i, sort_keys=True))
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    for p in Path(__file__).resolve().parents:
        if p.name == "gen":
            return p.parent


def _load_dep(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        spec = importlib.util.spec_from_file_location(
            module_name,
            base / module_name / "__init__.py",
            submodule_search_locations=[str(base / module_name)],
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


def _corpus_components(repo_root):
    root = Path(repo_root) / "specs" / "components"
    found = []
    if root.is_dir():
        for d in sorted(root.iterdir()):
            md = d / "component.md"
            if md.is_file():
                fm = _frontmatter(md)
                found.append((fm.get("id"), fm))
    return found


# ---------------------------------------------------------------------------
# check_readiness (R-TRACK-009/010/011/012)
# ---------------------------------------------------------------------------

def _check_component(pc, cid, repo_root, reasons):
    sealed_key = pc.current_sealed_key(cid, repo_root)
    if sealed_key is not None:
        result = pc.check_sealed_provenance(cid, repo_root)
        if not _get(result, "hit"):
            reasons.append(
                f"{cid}: sealed provenance {_get(result, 'reason')} "
                f"\u2014 run hotdocs generate {cid}"
            )
        return result

    key = pc.current_provenance_key(cid, repo_root)
    result = pc.check_provenance(
        cid, _get(key, "spec_bundle_hash"), _get(key, "gate_versions"), repo_root
    )
    if not _get(result, "hit"):
        reasons.append(
            f"{cid}: no provenance for current spec state "
            f"\u2014 run hotdocs generate {cid}"
        )
        return result

    report = _get(result, "verification_report")
    if _get(report, "overall") != "pass":
        rr = _get(report, "requirement_results") or {}
        fails = [rid for rid, v in rr.items() if v == "fail"]
        msg = f"{cid}: verification failed"
        if fails:
            msg += ": " + ", ".join(fails)
        reasons.append(msg)
    if _get(_get(result, "license_scan"), "blocked"):
        reasons.append(f"{cid}: license_scan blocked")
    if _get(_get(result, "secret_scan"), "flagged"):
        reasons.append(f"{cid}: secret_scan blocked")
    return result


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    pc = _load_dep("provenance-checker", "provenance_checker", repo_root)
    corpus = _corpus_components(repo_root)
    reasons = []

    if changed_ids:
        scope = "blast-radius"
        ia = _load_dep("impact-analyzer", "impact_analyzer", repo_root)
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
        scope_ids = [_get(e, "component_id") for e in (_get(blast, "impacted") or [])]
    else:
        scope = "whole-corpus"
        scope_ids = [cid for cid, _fm in corpus]

    components = {}
    for cid in scope_ids:
        components[cid] = _check_component(pc, cid, repo_root, reasons)

    in_scope = set(scope_ids)
    cap_ids = sorted({
        cap
        for cid, fm in corpus
        if cid in in_scope
        for cap in (fm.get("realizes") or [])
    })

    capabilities = {}
    if cap_ids:
        csv = _load_dep(
            "capability-scenario-verifier", "capability_scenario_verifier", repo_root
        )
        for cap in cap_ids:
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
                scenarios = _get(entry, "scenarios") or []
                if not scenarios:
                    reasons.append(
                        f"{cap}: has no capability scenarios; add a CS- scenario "
                        f"to its file under specs/product/"
                    )
                else:
                    failed = [
                        _get(s, "id") for s in scenarios if _get(s, "result") == "fail"
                    ]
                    reasons.append(
                        f"{cap}: capability scenarios failed: {', '.join(failed)}"
                    )

    return VerifyReport(
        scope=scope,
        ready=not reasons,
        components=components,
        capabilities=capabilities,
        not_ready_reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Attempt records (R-TRACK-004/007/008)
# ---------------------------------------------------------------------------

def _attempts_dir(component_id, repo_root):
    return Path(repo_root) / ".hotdocs" / "attempts" / component_id


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    directory = _attempts_dir(component_id, repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    same_second = len(list(directory.glob(f"{timestamp}-*.json")))
    attempt_id = f"{timestamp}-{same_second:06x}"
    record = AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=to_json(generation_result),
        verification=to_json(verification_report),
    )
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
    return record


def _is_feedback(rid, criteria):
    unsound = [
        c for c in criteria
        if c.get("covers") == rid and c.get("result") != "pass"
    ]
    if not unsound:
        return True
    return not all(
        c.get("failure_origin", "implementation") in ("test", "environment")
        for c in unsound
    )


def last_requirement_failures(component_id, repo_root):
    directory = _attempts_dir(component_id, repo_root)
    if not directory.is_dir():
        return []
    for path in sorted(directory.glob("*.json"), reverse=True):
        record = json.loads(path.read_text(encoding="utf-8"))
        verification = record.get("verification")
        if verification is None:
            continue
        results = verification.get("requirement_results") or {}
        criteria = verification.get("criteria") or []
        return sorted(
            rid for rid, v in results.items()
            if v == "fail" and _is_feedback(rid, criteria)
        )
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _UsageError(Exception):
    pass


def _parse(tokens, flags, repeatable=()):
    values = {}
    positionals = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--") and "=" in tok:
            name, val = tok[2:].split("=", 1)
            if name not in flags:
                raise _UsageError(f"unknown argument: {tok}")
        elif tok.startswith("--") and tok[2:] in flags:
            name = tok[2:]
            if i + 1 >= len(tokens):
                raise _UsageError(f"{tok} requires a value")
            i += 1
            val = tokens[i]
        elif tok.startswith("-"):
            raise _UsageError(f"unknown argument: {tok}")
        else:
            positionals.append(tok)
            i += 1
            continue
        if name in repeatable:
            values.setdefault(name, []).append(val)
        else:
            values[name] = val
        i += 1
    return values, positionals


def _usage_error(cause, usage):
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _verify(tokens):
    try:
        values, positionals = _parse(
            tokens, ("changed", "model", "seed", "repo-root", "format"), ("changed",)
        )
        if positionals:
            raise _UsageError(f"unknown argument: {positionals[0]}")
        try:
            seed = int(values.get("seed", "0"))
        except ValueError:
            raise _UsageError(f"--seed must be an integer: {values['seed']}")
        fmt = values.get("format", "text")
        if fmt not in ("json", "text"):
            raise _UsageError(f"invalid --format: {fmt}")
    except _UsageError as exc:
        return _usage_error(exc, VERIFY_USAGE)

    report = check_readiness(
        Path(values.get("repo-root", ".")),
        values.get("changed"),
        values.get("model"),
        seed,
    )
    ready = _get(report, "ready")
    if fmt == "json":
        print(json.dumps(to_json(report), sort_keys=True))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _feedback(tokens):
    try:
        values, positionals = _parse(tokens, ("repo-root",))
        if not positionals:
            raise _UsageError("missing <component-id>")
        if len(positionals) > 1:
            raise _UsageError(f"unknown argument: {positionals[1]}")
    except _UsageError as exc:
        return _usage_error(exc, FEEDBACK_USAGE)

    failures = last_requirement_failures(
        positionals[0], Path(values.get("repo-root", "."))
    )
    if failures:
        print(",".join(failures))
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv and argv[0] == "verify":
        return _verify(argv[1:])
    if len(argv) >= 2 and argv[0] == "track" and argv[1] == "feedback":
        return _feedback(argv[2:])
    word = " ".join(argv[:2]) if argv else "(none)"
    return _usage_error(
        f"unknown command: {word}", VERIFY_USAGE + "\n" + FEEDBACK_USAGE
    )
