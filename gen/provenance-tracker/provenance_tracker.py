"""Provenance tracker: `hotdocs verify` readiness checks and AttemptRecord history.

R-TRACK-004/007/008/009/010/011/012.
"""

import dataclasses
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, key):
    """Dual dict-or-attribute access (R-TRACK-012)."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _plain(value):
    """Recursively convert a value to plain JSON values (R-TRACK-007)."""
    if dataclasses.is_dataclass(value):
        return _plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return _plain(vars(value))


def _load(repo_root, slug, module_name):
    """Load a dependency from <repo_root>/gen/<slug>/, else the tool root's (R-TRACK-011)."""
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        tool_root = next(
            p.parent for p in Path(__file__).resolve().parents if p.name == "gen"
        )
        base = tool_root / "gen" / slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg_dir = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _scan_components(repo_root):
    """Every specs/components/*/component.md as (id, realizes), by frontmatter."""
    corpus = []
    for md in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        frontmatter = yaml.safe_load(md.read_text(encoding="utf-8").split("---", 2)[1])
        corpus.append((frontmatter["id"], frontmatter.get("realizes") or []))
    return corpus


def _generated_reasons(cid, result):
    """not_ready_reasons for a non-sealed component's ProvenanceCheckResult."""
    if not _get(result, "hit"):
        return [
            f"{cid}: no provenance for current spec state — run hotdocs generate {cid}"
        ]
    reasons = []
    report = _get(result, "verification_report")
    if _get(report, "overall") != "pass":
        results = _get(report, "requirement_results") or {}
        failing = [rid for rid, status in results.items() if status == "fail"]
        reasons.append(
            f"{cid}: verification failed — failing requirements: {', '.join(failing)}"
        )
    if _get(_get(result, "license_scan"), "blocked"):
        reasons.append(f"{cid}: license_scan blocked")
    if _get(_get(result, "secret_scan"), "flagged"):
        reasons.append(f"{cid}: secret_scan flagged")
    return reasons


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    """Would a merge pass right now (R-TRACK-009/010)."""
    repo_root = Path(repo_root)
    checker = _load(repo_root, "provenance-checker", "provenance_checker")
    corpus = _scan_components(repo_root)

    if changed_ids:
        scope = "blast-radius"
        analyzer = _load(repo_root, "impact-analyzer", "impact_analyzer")
        blast = analyzer.compute_blast_radius(list(changed_ids), repo_root)
        component_ids = [_get(entry, "component_id") for entry in _get(blast, "impacted")]
    else:
        scope = "whole-corpus"
        component_ids = [cid for cid, _ in corpus]

    components = {}
    reasons = []
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
            reasons.extend(_generated_reasons(cid, result))
        else:
            result = checker.check_sealed_provenance(cid, repo_root)
            components[cid] = result
            if not _get(result, "hit"):
                reasons.append(
                    f"{cid}: sealed provenance {_get(result, 'reason')} — "
                    f"run hotdocs generate {cid}"
                )

    in_scope = set(component_ids)
    capability_ids = sorted(
        {cap for cid, realizes in corpus if cid in in_scope for cap in realizes}
    )

    capabilities = {}
    if capability_ids:
        verifier = _load(
            repo_root, "capability-scenario-verifier", "capability_scenario_verifier"
        )
        for cap in capability_ids:
            result = verifier.check_capability_provenance(cap, repo_root)
            if not _get(result, "hit"):
                if model is None:
                    raise ValueError(
                        f"capability {cap} needs a fresh run but no model was given"
                    )
                result = verifier.run_capability_gates(
                    cap, repo_root, model, seed, llm_backend
                )
            capabilities[cap] = result
            overall = _get(_get(_get(result, "capability_scenario_report"), cap), "overall")
            if overall != "pass":
                reasons.append(
                    f"{cap}: capability scenarios not passing (overall: {overall})"
                )

    return {
        "scope": scope,
        "ready": not reasons,
        "components": components,
        "capabilities": capabilities,
        "not_ready_reasons": reasons,
    }


def write_attempt_record(
    component_id, generation_result, verification_report, spec_bundle_hash, repo_root
):
    """Write one AttemptRecord to .hotdocs/attempts/<component_id>/ (R-TRACK-007)."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{now.microsecond:06d}"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": timestamp,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{attempt_id}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    return record


def last_requirement_failures(component_id, repo_root):
    """Failing R-ids from the most recent AttemptRecord with verification (R-TRACK-008)."""
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    for path in sorted(directory.glob("*.json"), reverse=True):
        record = json.loads(path.read_text(encoding="utf-8"))
        verification = record.get("verification")
        if verification is not None:
            return [
                rid
                for rid, status in verification["requirement_results"].items()
                if status == "fail"
            ]
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse(args, flags):
    options = {}
    positionals = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            name, eq, value = arg[2:].partition("=")
            if name not in flags:
                raise _UsageError(f"unknown argument: {arg}")
            if not eq:
                i += 1
                if i >= len(args):
                    raise _UsageError(f"--{name} needs a value")
                value = args[i]
            options.setdefault(name, []).append(value)
        else:
            positionals.append(arg)
        i += 1
    return options, positionals


def _verify(args):
    options, positionals = _parse(
        args, {"changed", "model", "seed", "repo-root", "format"}
    )
    if positionals:
        raise _UsageError(f"unknown argument: {positionals[0]}")
    try:
        seed = int(options.get("seed", ["0"])[-1])
    except ValueError:
        raise _UsageError("--seed must be an integer") from None
    fmt = options.get("format", ["text"])[-1]
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")
    repo_root = Path(options.get("repo-root", [str(Path.cwd())])[-1])
    model = options.get("model", [None])[-1]
    try:
        report = check_readiness(
            repo_root, changed_ids=options.get("changed"), model=model, seed=seed
        )
    except ValueError as exc:
        raise _UsageError(str(exc)) from None
    ready = _get(report, "ready")
    if fmt == "json":
        print(json.dumps(_plain(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons"):
            print(reason)
    return 0 if ready else 1


def _feedback(args):
    options, positionals = _parse(args, {"repo-root"})
    if not positionals:
        raise _UsageError("missing <component-id>")
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument: {positionals[1]}")
    repo_root = Path(options.get("repo-root", [str(Path.cwd())])[-1])
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
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
