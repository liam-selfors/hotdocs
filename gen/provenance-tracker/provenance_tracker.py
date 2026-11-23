"""Provenance tracker: `hotdocs verify` readiness checks and attempt history."""

from __future__ import annotations

import dataclasses
import datetime
import enum
import importlib.util
import json
import math
import pathlib
import re
import sys
from collections.abc import Mapping
from pathlib import Path

import yaml


_USAGE_VERIFY = (
    "usage: hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
_USAGE_FEEDBACK = "usage: hotdocs track feedback <component-id> [--repo-root=<dir>]"
_USAGE_ALL = _USAGE_VERIFY + "\n" + _USAGE_FEEDBACK


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class VerifyReport:
    scope: str
    ready: bool
    components: dict
    capabilities: dict
    not_ready_reasons: list

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        return {
            "scope": self.scope,
            "ready": self.ready,
            "components": self.components,
            "capabilities": self.capabilities,
            "not_ready_reasons": self.not_ready_reasons,
        }


@dataclasses.dataclass
class AttemptRecord:
    attempt_id: str
    component_id: str
    timestamp: str
    spec_bundle_hash: str
    generation: object
    verification: object

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        return {
            "attempt_id": self.attempt_id,
            "component_id": self.component_id,
            "timestamp": self.timestamp,
            "spec_bundle_hash": self.spec_bundle_hash,
            "generation": self.generation,
            "verification": self.verification,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, key, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_json(value):
    """Convert a value to plain JSON values (specs/architecture/json-values.md)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
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


def _tool_root():
    return next(
        d.parent for d in Path(__file__).resolve().parents if d.name == "gen"
    )


def _load_dep(slug, module_name, repo_root):
    """Load a dependency afresh from <repo_root>/gen/<slug>/, else the tool root's."""
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module_name}.py"
    search = None
    if not path.is_file():
        path = base / module_name / "__init__.py"
        search = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(
        module_name, str(path), submodule_search_locations=search
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


def _frontmatter(path):
    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    return (yaml.safe_load(match.group(1)) if match else None) or {}


def _component_entries(repo_root):
    """(component_id, realizes list) for every specs/components/*/component.md."""
    entries = []
    for path in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(path)
        realizes = fm.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        entries.append((fm.get("id"), list(realizes)))
    return entries


# ---------------------------------------------------------------------------
# check_readiness
# ---------------------------------------------------------------------------


def _check_component(checker, component_id, repo_root, components, reasons):
    sealed_key = checker.current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        result = checker.check_sealed_provenance(component_id, repo_root)
        components[component_id] = result
        if not _get(result, "hit"):
            reasons.append(
                f"{component_id}: sealed provenance {_get(result, 'reason')} "
                f"— run hotdocs generate {component_id}"
            )
        return

    key = checker.current_provenance_key(component_id, repo_root)
    result = checker.check_provenance(
        component_id,
        _get(key, "spec_bundle_hash"),
        _get(key, "gate_versions"),
        repo_root,
    )
    components[component_id] = result
    if not _get(result, "hit"):
        reasons.append(
            f"{component_id}: no provenance for current spec state "
            f"— run hotdocs generate {component_id}"
        )
        return

    report = _get(result, "verification_report")
    if _get(report, "overall") != "pass":
        failing = [
            rid
            for rid, verdict in (_get(report, "requirement_results") or {}).items()
            if verdict == "fail"
        ]
        reasons.append(
            f"{component_id}: verification failed"
            + (f": {', '.join(failing)}" if failing else "")
        )
    if _get(_get(result, "license_scan"), "blocked"):
        reasons.append(f"{component_id}: license_scan blocked")
    if _get(_get(result, "secret_scan"), "flagged"):
        reasons.append(f"{component_id}: secret_scan flagged")


def _capability_reason(capability_id, result):
    entry = _get(_get(result, "capability_scenario_report"), capability_id)
    if _get(entry, "overall") == "pass":
        return None
    scenarios = _get(entry, "scenarios") or []
    if not scenarios:
        return (
            f"{capability_id}: has no capability scenarios; "
            "add a CS- scenario to its file under specs/product/"
        )
    failed = [_get(s, "id") for s in scenarios if _get(s, "result") == "fail"]
    return f"{capability_id}: capability scenarios failed: {', '.join(failed)}"


def check_readiness(
    repo_root: Path,
    changed_ids: list[str] | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
) -> VerifyReport:
    repo_root = Path(repo_root)
    checker = _load_dep("provenance-checker", "provenance_checker", repo_root)
    components: dict = {}
    capabilities: dict = {}
    reasons: list = []
    entries = _component_entries(repo_root)

    if changed_ids:
        scope = "blast-radius"
        analyzer = _load_dep("impact-analyzer", "impact_analyzer", repo_root)
        blast = analyzer.compute_blast_radius(list(changed_ids), repo_root)
        error = _get(blast, "precondition_error")
        if error is not None:
            return VerifyReport(
                scope=scope,
                ready=False,
                components={},
                capabilities={},
                not_ready_reasons=[f"blast radius unavailable: {error}"],
            )
        component_ids = [
            _get(entry, "component_id") for entry in (_get(blast, "impacted") or [])
        ]
    else:
        scope = "whole-corpus"
        component_ids = [cid for cid, _ in entries]

    for component_id in component_ids:
        _check_component(checker, component_id, repo_root, components, reasons)

    in_scope = set(component_ids)
    capability_ids = sorted(
        {cap for cid, realizes in entries if cid in in_scope for cap in realizes}
    )
    if capability_ids:
        verifier = _load_dep(
            "capability-scenario-verifier", "capability_scenario_verifier", repo_root
        )
        for capability_id in capability_ids:
            result = verifier.check_capability_provenance(capability_id, repo_root)
            if not _get(result, "hit"):
                if model is None:
                    capabilities[capability_id] = result
                    reasons.append(f"{capability_id}: needs a fresh run; pass --model")
                    continue
                result = verifier.run_capability_gates(
                    capability_id, repo_root, model, seed, llm_backend
                )
            capabilities[capability_id] = result
            reason = _capability_reason(capability_id, result)
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
# Attempt history
# ---------------------------------------------------------------------------


def write_attempt_record(
    component_id: str,
    generation_result,
    verification_report,
    spec_bundle_hash: str,
    repo_root: Path,
) -> AttemptRecord:
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{now.microsecond:06d}"
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
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), indent=2))
    return record


def last_requirement_failures(component_id: str, repo_root: Path) -> list[str]:
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    for path in sorted(directory.glob("*.json"), reverse=True):
        verification = json.loads(path.read_text(encoding="utf-8")).get("verification")
        if verification is None:
            continue
        criteria = verification.get("criteria") or []
        failures = []
        for rid, verdict in (verification.get("requirement_results") or {}).items():
            if verdict != "fail":
                continue
            covering = [
                c for c in criteria
                if c.get("covers") == rid and c.get("result") != "pass"
            ]
            if covering and all(
                c.get("failure_origin", "implementation") in ("test", "environment")
                for c in covering
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


def _parse(tokens, flags):
    values = {flag: [] for flag in flags}
    positionals = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, eq, value = token.partition("=")
        if eq and name in flags:
            values[name].append(value)
        elif token in flags:
            if i + 1 >= len(tokens):
                raise _UsageError(f"{token} requires a value")
            i += 1
            values[token].append(tokens[i])
        elif token.startswith("-"):
            raise _UsageError(f"unknown argument: {token}")
        else:
            positionals.append(token)
        i += 1
    return values, positionals


def _verify(tokens):
    values, positionals = _parse(
        tokens, ("--changed", "--model", "--seed", "--repo-root", "--format")
    )
    if positionals:
        raise _UsageError(f"unknown argument: {positionals[0]}")
    fmt = (values["--format"] or ["text"])[-1]
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")
    seed_text = (values["--seed"] or ["0"])[-1]
    try:
        seed = int(seed_text)
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {seed_text}") from None
    model = (values["--model"] or [None])[-1]
    repo_root = Path((values["--repo-root"] or ["."])[-1])

    report = check_readiness(repo_root, values["--changed"] or None, model, seed)
    ready = bool(_get(report, "ready"))
    if fmt == "json":
        print(json.dumps(_to_json(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _feedback(tokens):
    values, positionals = _parse(tokens, ("--repo-root",))
    if not positionals:
        raise _UsageError("missing <component-id>")
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument: {positionals[1]}")
    repo_root = Path((values["--repo-root"] or ["."])[-1])
    failures = last_requirement_failures(positionals[0], repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    usage = _USAGE_ALL
    try:
        if argv[:1] == ["verify"]:
            usage = _USAGE_VERIFY
            return _verify(argv[1:])
        if argv[:2] == ["track", "feedback"]:
            usage = _USAGE_FEEDBACK
            return _feedback(argv[2:])
        raise _UsageError("expected 'verify' or 'track feedback'")
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(usage, file=sys.stderr)
        return 2
