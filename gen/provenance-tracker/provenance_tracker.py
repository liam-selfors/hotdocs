"""provenance-tracker: `hotdocs verify` readiness checks and AttemptRecord history.

R-TRACK-004, R-TRACK-007 .. R-TRACK-012.
"""

import dataclasses
import importlib.util
import json
import sys
import uuid  # noqa: F401  (kept for parity with attempt-id generation helpers)
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, name):
    """Dual dict-or-attribute access (R-TRACK-012)."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _plain(value):
    """Recursively convert a value to plain JSON values (R-TRACK-007)."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float)):
        return value
    if dataclasses.is_dataclass(value):
        return _plain(dataclasses.asdict(value))
    return _plain(vars(value))


def _tool_root():
    """The parent of the nearest directory named `gen` above this module."""
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load(repo_root, slug, module_name):
    """Load a dependency module from `repo_root`, else the tool root (R-TRACK-011)."""
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module_name}.py"
    locations = None
    if not path.is_file():
        path = base / module_name / "__init__.py"
        locations = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(path):
    """Parse a component.md's YAML frontmatter with yaml.safe_load."""
    lines = path.read_text(encoding="utf-8").splitlines()
    end = lines.index("---", 1)
    return yaml.safe_load("\n".join(lines[1:end]))


# ---------------------------------------------------------------------------
# check_readiness (R-TRACK-009 / R-TRACK-010)
# ---------------------------------------------------------------------------

def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    checker = _load(repo_root, "provenance-checker", "provenance_checker")

    corpus = [
        _frontmatter(p)
        for p in sorted((Path(repo_root) / "specs" / "components").glob("*/component.md"))
    ]

    if changed_ids:
        scope = "blast-radius"
        analyzer = _load(repo_root, "impact-analyzer", "impact_analyzer")
        blast = analyzer.compute_blast_radius(changed_ids, repo_root)
        component_ids = [_get(entry, "component_id") for entry in _get(blast, "impacted")]
    else:
        scope = "whole-corpus"
        component_ids = [fm["id"] for fm in corpus]

    components = {}
    reasons = []

    for cid in component_ids:
        sealed_key = checker.current_sealed_key(cid, repo_root)
        if sealed_key is None:
            key = checker.current_provenance_key(cid, repo_root)
            result = checker.check_provenance(
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
                failing = [
                    rid
                    for rid, status in _get(report, "requirement_results").items()
                    if status == "fail"
                ]
                reasons.append(f"{cid}: verification failed ({', '.join(failing)})")
            if _get(_get(result, "license_scan"), "blocked"):
                reasons.append(f"{cid}: license_scan blocked")
            if _get(_get(result, "secret_scan"), "flagged"):
                reasons.append(f"{cid}: secret_scan flagged")
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
        {
            cap
            for fm in corpus
            if fm["id"] in in_scope
            for cap in (fm.get("realizes") or [])
        }
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
                reasons.append(f"{cap}: capability scenarios not passing (overall: {overall})")

    return {
        "scope": scope,
        "ready": not reasons,
        "components": components,
        "capabilities": capabilities,
        "not_ready_reasons": reasons,
    }


# ---------------------------------------------------------------------------
# AttemptRecord history (R-TRACK-004 / R-TRACK-007 / R-TRACK-008)
# ---------------------------------------------------------------------------

def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
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
    with open(directory / f"{attempt_id}.json", "x", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=2))
    return record


def last_requirement_failures(component_id, repo_root):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    for path in sorted(directory.glob("*.json"), reverse=True):
        verification = json.loads(path.read_text(encoding="utf-8")).get("verification")
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

def _parse(args, flags):
    values = {flag: [] for flag in flags}
    positionals = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            name, eq, value = arg.partition("=")
            if name not in values:
                raise ValueError(f"unknown argument: {arg}")
            if not eq:
                i += 1
                if i >= len(args):
                    raise ValueError(f"{name} needs a value")
                value = args[i]
            values[name].append(value)
        else:
            positionals.append(arg)
        i += 1
    return values, positionals


def _verify(args):
    values, positionals = _parse(
        args, ["--changed", "--model", "--seed", "--repo-root", "--format"]
    )
    if positionals:
        raise ValueError(f"unknown argument: {positionals[0]}")
    model = (values["--model"] or [None])[-1]
    seed = int((values["--seed"] or ["0"])[-1])
    repo_root = Path((values["--repo-root"] or ["."])[-1])
    fmt = (values["--format"] or ["text"])[-1]
    if fmt not in ("text", "json"):
        raise ValueError(f"invalid --format: {fmt}")
    report = check_readiness(
        repo_root, changed_ids=values["--changed"] or None, model=model, seed=seed
    )
    ready = _get(report, "ready")
    if fmt == "json":
        print(json.dumps(_plain(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons"):
            print(reason)
    return 0 if ready else 1


def _feedback(args):
    values, positionals = _parse(args, ["--repo-root"])
    if len(positionals) != 1:
        raise ValueError("expected exactly one <component-id>")
    repo_root = Path((values["--repo-root"] or ["."])[-1])
    failures = last_requirement_failures(positionals[0], repo_root)
    if failures:
        print(",".join(failures))
    return 0


def main(argv):
    try:
        if argv[:1] == ["verify"]:
            return _verify(argv[1:])
        if argv[:2] == ["track", "feedback"]:
            return _feedback(argv[2:])
    except ValueError:
        return 2
    return 2
