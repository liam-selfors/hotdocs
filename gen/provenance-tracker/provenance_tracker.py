"""Provenance tracker: `hotdocs verify` readiness checks and attempt history.

Answers "would a merge pass right now" by checking every in-scope
component's provenance (read-only, via provenance-checker) and
checking-then-running every intersecting capability's scenarios (via
capability-scenario-verifier), and keeps an append-only local history of
`hotdocs generate` attempts under `.hotdocs/attempts/<component_id>/`.
"""

from __future__ import annotations

import dataclasses
import enum
import importlib.util
import json
import math
import pathlib
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml


VERIFY_USAGE = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
FEEDBACK_USAGE = "usage: hotdocs track feedback <component-id> [--repo-root=<dir>]"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class _ItemAccess:
    """Lets a dataclass result be read by item as well as by attribute."""

    def __getitem__(self, key):
        return getattr(self, key)


@dataclass
class AttemptRecord(_ItemAccess):
    attempt_id: str
    component_id: str
    timestamp: str
    spec_bundle_hash: str
    generation: object
    verification: object


@dataclass
class VerifyReport(_ItemAccess):
    scope: str
    ready: bool
    components: dict = field(default_factory=dict)
    capabilities: dict = field(default_factory=dict)
    not_ready_reasons: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def to_json(value):
    """Convert a value to plain JSON values (specs/architecture/json-values.md)."""
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


def _tool_root() -> Path:
    here = Path(__file__).resolve().parent
    return next(d.parent for d in (here, *here.parents) if d.name == "gen")


def _load_dep(repo_root, slug: str, module_name: str):
    """Load a dependency module afresh from repo_root (else the tool root)."""
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module_name}.py"
    if not path.is_file():
        path = base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    end = lines.index("---", 1)
    return yaml.safe_load("\n".join(lines[1:end])) or {}


def _corpus_components(repo_root: Path) -> list:
    """(id, realizes) for every specs/components/*/component.md, by directory name."""
    entries = []
    for comp_md in sorted((Path(repo_root) / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(comp_md)
        entries.append((fm.get("id"), fm.get("realizes") or []))
    return entries


# ---------------------------------------------------------------------------
# check_readiness
# ---------------------------------------------------------------------------


def _check_component(pc, cid, repo_root, components, reasons):
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
            return
        report = _get(result, "verification_report")
        if _get(report, "overall") != "pass":
            failing = [
                r for r, v in (_get(report, "requirement_results") or {}).items() if v == "fail"
            ]
            reason = f"{cid}: verification failed"
            if failing:
                reason += ": " + ", ".join(failing)
            reasons.append(reason)
        if _get(_get(result, "license_scan"), "blocked"):
            reasons.append(f"{cid}: license_scan blocked")
        if _get(_get(result, "secret_scan"), "flagged"):
            reasons.append(f"{cid}: secret_scan flagged")
        return
    result = pc.check_sealed_provenance(cid, repo_root)
    components[cid] = result
    if not _get(result, "hit"):
        reasons.append(
            f"{cid}: sealed provenance {_get(result, 'reason')} — run hotdocs generate {cid}"
        )


def _capability_reason(cap_id, result):
    entry = _get(_get(result, "capability_scenario_report"), cap_id)
    if _get(entry, "overall") == "pass":
        return None
    scenarios = _get(entry, "scenarios")
    if not scenarios:
        return (
            f"{cap_id}: has no capability scenarios; "
            "add a CS- scenario to its file under specs/product/"
        )
    failed = [_get(s, "id") for s in scenarios if _get(s, "result") == "fail"]
    return f"{cap_id}: capability scenarios failed: {', '.join(failed)}"


def check_readiness(
    repo_root: Path,
    changed_ids: list | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
) -> VerifyReport:
    pc = _load_dep(repo_root, "provenance-checker", "provenance_checker")
    corpus = _corpus_components(repo_root)

    if changed_ids:
        scope = "blast-radius"
        ia = _load_dep(repo_root, "impact-analyzer", "impact_analyzer")
        blast = ia.compute_blast_radius(list(changed_ids), repo_root)
        precondition_error = _get(blast, "precondition_error")
        if precondition_error is not None:
            return VerifyReport(
                scope=scope,
                ready=False,
                components={},
                capabilities={},
                not_ready_reasons=[f"blast radius unavailable: {precondition_error}"],
            )
        component_ids = [_get(e, "component_id") for e in _get(blast, "impacted")]
    else:
        scope = "whole-corpus"
        component_ids = [cid for cid, _ in corpus]

    components: dict = {}
    reasons: list = []
    for cid in component_ids:
        _check_component(pc, cid, repo_root, components, reasons)

    in_scope = set(component_ids)
    realized_by: dict = {}
    for cid, realizes in corpus:
        for cap_id in realizes:
            realized_by.setdefault(cap_id, set()).add(cid)
    cap_ids = sorted(c for c, comps in realized_by.items() if comps & in_scope)

    capabilities: dict = {}
    if cap_ids:
        csv = _load_dep(
            repo_root, "capability-scenario-verifier", "capability_scenario_verifier"
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

    return VerifyReport(
        scope=scope,
        ready=not reasons,
        components=components,
        capabilities=capabilities,
        not_ready_reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Attempt records
# ---------------------------------------------------------------------------


def _attempts_dir(component_id: str, repo_root) -> Path:
    return Path(repo_root) / ".hotdocs" / "attempts" / component_id


def write_attempt_record(
    component_id: str,
    generation_result,
    verification_report,
    spec_bundle_hash: str,
    repo_root: Path,
) -> AttemptRecord:
    directory = _attempts_dir(component_id, repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sequence = len(list(directory.glob("*.json")))
    attempt_id = f"{timestamp}-{sequence:06x}"
    record = AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=to_json(generation_result),
        verification=to_json(verification_report),
    )
    (directory / f"{attempt_id}.json").write_text(
        json.dumps(to_json(record), indent=2) + "\n", encoding="utf-8"
    )
    return record


def last_requirement_failures(component_id: str, repo_root: Path) -> list:
    for path in sorted(_attempts_dir(component_id, repo_root).glob("*.json"), reverse=True):
        verification = json.loads(path.read_text(encoding="utf-8")).get("verification")
        if verification is None:
            continue
        criteria = verification.get("criteria") or []
        failures = []
        for r_id, outcome in (verification.get("requirement_results") or {}).items():
            if outcome != "fail":
                continue
            origins = [
                c.get("failure_origin", "implementation")
                for c in criteria
                if c.get("covers") == r_id and c.get("result") != "pass"
            ]
            if origins and all(o in ("test", "environment") for o in origins):
                continue
            failures.append(r_id)
        return sorted(failures)
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse(tokens, flags):
    values: dict = {}
    positionals: list = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            name, eq, val = tok.partition("=")
            if name not in flags:
                raise _UsageError(f"unknown argument: {tok}")
            if not eq:
                if i + 1 >= len(tokens):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                val = tokens[i]
            values.setdefault(name, []).append(val)
        else:
            positionals.append(tok)
        i += 1
    return values, positionals


def _usage_error(cause: str, usage: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _main_verify(tokens) -> int:
    try:
        values, positionals = _parse(
            tokens, {"--changed", "--model", "--seed", "--repo-root", "--format"}
        )
        if positionals:
            raise _UsageError(f"unknown argument: {positionals[0]}")
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

    repo_root = Path(values["--repo-root"][-1]) if "--repo-root" in values else Path.cwd()
    model = values["--model"][-1] if "--model" in values else None
    changed = values.get("--changed") or None
    result = check_readiness(repo_root, changed_ids=changed, model=model, seed=seed)
    ready = bool(_get(result, "ready"))
    if fmt == "json":
        print(json.dumps(to_json(result)))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(result, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _main_feedback(tokens) -> int:
    try:
        values, positionals = _parse(tokens, {"--repo-root"})
        if not positionals:
            raise _UsageError("missing <component-id>")
        if len(positionals) > 1:
            raise _UsageError(f"unknown argument: {positionals[1]}")
    except _UsageError as exc:
        return _usage_error(str(exc), FEEDBACK_USAGE)

    repo_root = Path(values["--repo-root"][-1]) if "--repo-root" in values else Path.cwd()
    failures = last_requirement_failures(positionals[0], repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:1] == ["verify"]:
        return _main_verify(argv[1:])
    if argv[:2] == ["track", "feedback"]:
        return _main_feedback(argv[2:])
    return _usage_error(
        f"unknown command: {' '.join(argv[:2])}",
        VERIFY_USAGE + "\n" + FEEDBACK_USAGE,
    )
