"""Provenance Tracker: `hotdocs verify` readiness checks and attempt records."""

from __future__ import annotations

import dataclasses
import datetime
import enum
import importlib.util
import json
import math
import re
import sys
import time
from collections.abc import Mapping
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
        return sorted(
            (to_json(v) for v in value),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    try:
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
    except Exception:
        pass
    return repr(value)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    raise FileNotFoundError("no directory named gen above " + __file__)


def _load(slug: str, module_name: str, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module_name}.py"
    kwargs = {}
    if not path.is_file():
        path = base / module_name / "__init__.py"
        kwargs["submodule_search_locations"] = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(module_name, path, **kwargs)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


def _frontmatter(path: Path) -> dict:
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    return (yaml.safe_load(match.group(1)) if match else None) or {}


def _component_frontmatters(repo_root) -> list:
    base = Path(repo_root) / "specs" / "components"
    return [_frontmatter(p) for p in sorted(base.glob("*/component.md"))]


# ---------------------------------------------------------------------------
# check_readiness
# ---------------------------------------------------------------------------

def check_readiness(
    repo_root: Path,
    changed_ids: list[str] | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
) -> VerifyReport:
    components: dict = {}
    capabilities: dict = {}
    reasons: list = []
    secret_scan = None
    frontmatters = _component_frontmatters(repo_root)

    if changed_ids:
        scope = "blast-radius"
        impact_analyzer = _load("impact-analyzer", "impact_analyzer", repo_root)
        blast = impact_analyzer.compute_blast_radius(changed_ids, repo_root)
        precondition_error = _get(blast, "precondition_error")
        if precondition_error is not None:
            return VerifyReport(
                scope=scope,
                ready=False,
                components={},
                capabilities={},
                secret_scan=None,
                not_ready_reasons=[
                    f"blast radius unavailable: {precondition_error}"
                ],
            )
        component_ids = [
            _get(entry, "component_id") for entry in (_get(blast, "impacted") or [])
        ]
    else:
        scope = "whole-corpus"
        component_ids = [fm.get("id") for fm in frontmatters if fm.get("id")]

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
                    f"{cid}: no provenance for current spec state — "
                    f"run hotdocs generate {cid}"
                )
                continue
            report = _get(result, "verification_report")
            if _get(report, "overall") != "pass":
                fails = [
                    rid
                    for rid, value in (_get(report, "requirement_results") or {}).items()
                    if value == "fail"
                ]
                reason = f"{cid}: verification failed"
                if fails:
                    reason += ": " + ", ".join(fails)
                reasons.append(reason)
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

    scope_set = set(component_ids)
    intersecting = sorted(
        {
            cap
            for fm in frontmatters
            if fm.get("id") in scope_set
            for cap in (fm.get("realizes") or [])
        }
    )
    if intersecting:
        verifier = _load(
            "capability-scenario-verifier", "capability_scenario_verifier", repo_root
        )
    for cap in intersecting:
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

    if component_ids:
        try:
            scanner = _load("secret-scanner", "secret_scanner", repo_root)
            scan_result = scanner.scan(repo_root)
        except Exception as exc:
            reasons.append(
                f"secret_scan unavailable: {type(exc).__name__}: {exc}"
            )
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
    ns = time.time_ns()
    moment = datetime.datetime.fromtimestamp(
        ns // 1_000_000_000, tz=datetime.timezone.utc
    )
    timestamp = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{ns % 1_000_000_000:09d}"
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
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=2))
    return record


def last_requirement_failures(component_id: str, repo_root: Path) -> list[str]:
    files = sorted(_attempts_dir(component_id, repo_root).glob("*.json"), reverse=True)
    for path in files:
        verification = json.loads(path.read_text(encoding="utf-8")).get("verification")
        if verification is None:
            continue
        criteria = verification.get("criteria") or []
        failing = []
        for rid, value in (verification.get("requirement_results") or {}).items():
            if value != "fail":
                continue
            not_passed = [
                c for c in criteria
                if c.get("covers") == rid and c.get("result") != "pass"
            ]
            if not_passed and all(
                c.get("failure_origin", "implementation") in ("test", "environment")
                for c in not_passed
            ):
                continue
            failing.append(rid)
        return sorted(failing)
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
        name, eq, val = tok.partition("=")
        if eq and name in flags:
            values.setdefault(name, []).append(val)
        elif tok in flags:
            if i + 1 >= len(tokens):
                raise _UsageError(f"{tok} requires a value")
            i += 1
            values.setdefault(tok, []).append(tokens[i])
        elif tok.startswith("-"):
            raise _UsageError(f"unknown argument: {tok}")
        else:
            positionals.append(tok)
        i += 1
    return values, positionals


def _usage_error(cause: str, usage: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _verify(tokens) -> int:
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
            raise _UsageError(f"--seed must be an integer: {seed_text}") from None
        fmt = values.get("--format", ["text"])[-1]
        if fmt not in ("json", "text"):
            raise _UsageError(f"invalid --format: {fmt}")
    except _UsageError as exc:
        return _usage_error(str(exc), VERIFY_USAGE)
    repo_root = Path(values["--repo-root"][-1]) if "--repo-root" in values else Path.cwd()
    model = values.get("--model", [None])[-1]
    changed = values.get("--changed") or None
    report = check_readiness(
        repo_root, changed_ids=changed, model=model, seed=seed
    )
    ready = bool(_get(report, "ready"))
    if fmt == "json":
        print(json.dumps(to_json(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)
    return 0 if ready else 1


def _feedback(tokens) -> int:
    try:
        values, positionals = _parse(tokens, {"--repo-root"})
        if not positionals:
            raise _UsageError("missing <component-id>")
        if len(positionals) > 1:
            raise _UsageError(f"unknown argument: {positionals[1]}")
    except _UsageError as exc:
        return _usage_error(str(exc), FEEDBACK_USAGE)
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
        return _verify(argv[1:])
    if argv[:2] == ["track", "feedback"]:
        return _feedback(argv[2:])
    first = " ".join(argv[:2]) if argv else "(none)"
    return _usage_error(f"unknown command: {first}", GENERAL_USAGE)
