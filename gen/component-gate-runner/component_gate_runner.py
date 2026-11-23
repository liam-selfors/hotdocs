"""Component Gate Runner: one component through its gauntlet (R-GATE-001..011)."""

import dataclasses
import enum
import importlib.util
import json
import math
import pathlib
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

USAGE = (
    "usage: hotdocs generate <component-id> --model=<model-id> [--seed=<n>] "
    "[--retry-feedback=<R-id>,...] [--max-attempts=<n>] [--mode=single|agentic] "
    "[--allow-unisolated-exec] [--repo-root=<dir>] [--format=json|text]"
)

_VALUE_FLAGS = (
    "--model",
    "--seed",
    "--retry-feedback",
    "--max-attempts",
    "--mode",
    "--repo-root",
    "--format",
)


def _get(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    return next(d.parent for d in Path(__file__).resolve().parents if d.name == "gen")


def _load(slug, repo_root):
    module = slug.replace("-", "_")
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module}.py"
    spec = importlib.util.spec_from_file_location(module, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _result(component_id, *, provenance_hit=False, reverified=False, blocked=False,
            block_reason=None, model_call_error=None, surface_report=None,
            verification=None, attempts=None, license_scan=None, secret_scan=None):
    return {
        "component_id": component_id,
        "provenance_hit": provenance_hit,
        "reverified": reverified,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": model_call_error,
        "surface_report": surface_report,
        "verification": verification,
        "attempts": [] if attempts is None else attempts,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _count_attempt_files(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file())


def _is_test_authoring_failure(report):
    failed = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    return bool(failed) and all(_get(c, "failure_origin") == "test" for c in failed)


def run_component_gates(
    component_id, repo_root, model, seed=0, llm_backend=None, retry_feedback=None, *,
    max_attempts=3, mode="single", allow_unisolated_exec=False,
):
    loaded = {}

    def dep(slug):
        if slug not in loaded:
            loaded[slug] = _load(slug, repo_root)
        return loaded[slug]

    def scans():
        lic = dep("license-scanner").scan(component_id, repo_root)
        sec = dep("secret-scanner").scan(repo_root)
        return lic, sec

    def reverify():
        test_author, judge = dep("generation-loop").make_closures(model, seed, repo_root, llm_backend)
        report = dep("verifier-orchestrator").verify(
            component_id, repo_root, judge=judge, test_author=test_author)
        lic, sec = scans()
        return report, lic, sec

    sealed = dep("provenance-checker").current_sealed_key(component_id, repo_root)
    if sealed is not None:
        report, lic, sec = reverify()
        inputs = {
            "component_id": component_id,
            "owners": _get(sealed, "owners"),
            "source_path": _get(sealed, "source_path"),
            "source_hash": _get(sealed, "source_hash"),
            "verifier_version": _get(sealed, "verifier_version"),
            "verification_report": report,
        }
        dep("provenance-writer").write_sealed_provenance(component_id, inputs, repo_root)
        failed = _get(report, "overall") == "fail"
        return _result(
            component_id, blocked=failed,
            block_reason="verification_failed" if failed else None,
            verification=report, license_scan=lic, secret_scan=sec)

    checker = dep("provenance-checker")
    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = checker.check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)

    hit_report = _get(check, "verification_report")
    hit_license = _get(check, "license_scan")
    if (_get(check, "hit") and _get(hit_report, "overall") == "pass"
            and _get(hit_license, "blocked") is not True):
        return _result(
            component_id, provenance_hit=True, verification=hit_report,
            license_scan=hit_license, secret_scan=_get(check, "secret_scan"))

    if _get(check, "reason") == "environment differs":
        report, lic, sec = reverify()
        if (_get(report, "overall") == "pass" and _get(lic, "blocked") is not True
                and _get(sec, "flagged") is not True):
            slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
            manifest_path = Path(repo_root) / "gen" / slug / ".provenance.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            generation_result = {
                "files": {},
                "spec_bundle_hash": spec_bundle_hash,
                "model": manifest.get("model_pin"),
                "prompt_version": manifest.get("prompt_version"),
                "retry_feedback": manifest.get("retry_feedback"),
            }
            for name, value in (manifest.get("generation") or {}).items():
                if name != "generator_version":
                    generation_result[name] = value
            inputs = {
                "component_id": component_id,
                "generation_result": generation_result,
                "verification_report": report,
                "license_scan_result": lic,
                "secret_scan_result": sec,
                "provenance_hit": False,
                "attempts": manifest.get("attempts"),
                "attempt_history": manifest.get("attempt_history"),
                "gate_versions": gate_versions,
            }
            dep("provenance-writer").write_provenance(component_id, inputs, repo_root)
            return _result(
                component_id, reverified=True, verification=report,
                license_scan=lic, secret_scan=sec)

    bundle = dep("spec-bundle-assembler").assemble(component_id, repo_root=repo_root, mode="cold")

    def on_attempt(attempt, generation_result, verification_report):
        try:
            dep("provenance-tracker").write_attempt_record(
                component_id, generation_result, verification_report,
                spec_bundle_hash, repo_root)
        except Exception:
            pass

    loop_result = dep("generation-loop").run_attempts(
        component_id, bundle, repo_root, model, mode=mode, max_attempts=max_attempts,
        retry_feedback=retry_feedback, seed=seed, llm_backend=llm_backend,
        allow_unisolated_exec=allow_unisolated_exec, on_attempt=on_attempt)

    attempts = _get(loop_result, "attempts")
    generation_result = _get(loop_result, "generation_result")
    verification_report = _get(loop_result, "verification_report")
    surface_report = _get(loop_result, "surface_report")

    lic, sec = scans()

    if _get(generation_result, "files") and verification_report is not None:
        inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": lic,
            "secret_scan_result": sec,
            "provenance_hit": False,
            "attempts": _count_attempt_files(repo_root, component_id),
            "attempt_history": attempts,
            "gate_versions": gate_versions,
        }
        dep("provenance-writer").write_provenance(component_id, inputs, repo_root)

    blocked = False
    block_reason = None
    model_call_error = None
    if not _get(loop_result, "passed"):
        blocked = True
        outcome = _get(attempts[-1], "outcome")
        if outcome == "generation_failed":
            block_reason = "model_call_error"
            model_call_error = _get(generation_result, "model_call_error")
        elif outcome == "surface_failed":
            block_reason = "surface_check_failed"
        elif outcome == "refused":
            block_reason = "refused"
        elif _is_test_authoring_failure(verification_report):
            block_reason = "test_authoring_failed"
        else:
            block_reason = "verification_failed"

    return _result(
        component_id, blocked=blocked, block_reason=block_reason,
        model_call_error=model_call_error, surface_report=surface_report,
        verification=verification_report, attempts=attempts,
        license_scan=lic, secret_scan=sec)


def to_json(value):
    """Convert `value` to plain JSON values (specs/architecture/json-values.md)."""
    try:
        if value is None or isinstance(value, (bool, int, str)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else repr(value)
        if isinstance(value, Mapping):
            return {(k if isinstance(k, str) else str(k)): to_json(v) for k, v in value.items()}
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
            return {f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
        if hasattr(value, "__dict__"):
            return {k: to_json(v) for k, v in vars(value).items()
                    if not k.startswith("_") and not callable(v)}
        return repr(value)
    except Exception:
        try:
            return repr(value)
        except Exception:
            return "<unrepresentable>"


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _valid_max_attempts(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _print_text(result):
    print(result["component_id"])
    if result["provenance_hit"]:
        print("provenance hit")
    elif result["reverified"]:
        print("reverified")
    else:
        print(result["block_reason"] or "passed")
    for attempt in result["attempts"] or []:
        print(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    lic = result["license_scan"]
    sec = result["secret_scan"]
    print(f"license_scan blocked: {json.dumps(to_json(_get(lic, 'blocked')))}")
    print(f"secret_scan flagged: {json.dumps(to_json(_get(sec, 'flagged')))}")
    mce = result["model_call_error"]
    if mce is not None:
        print(f"model_call_error: {_get(mce, 'category')}: {_get(mce, 'message')}")
    if result["block_reason"] == "surface_check_failed":
        for finding in _get(result["surface_report"], "findings") or []:
            print(f"surface: {_get(finding, 'message')}")
    report = result["verification"]
    if result["block_reason"] == "test_authoring_failed":
        for criterion in _get(report, "criteria") or []:
            if _get(criterion, "result") == "fail":
                detail = _get(criterion, "failure_detail")
                print(f"{_get(criterion, 'id')}: {_get(detail, 'message')}")
    mutation_error = _get(report, "mutation_error")
    if mutation_error:
        print(f"mutation_error: {mutation_error}")
    if _get(lic, "evaluated") is False:
        print(f"license_scan not evaluated: {_get(lic, 'reason')}")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv or argv[0] != "generate":
        return _usage_error("expected first word 'generate'")

    component_id = None
    opts = {}
    allow_unisolated_exec = False
    i = 1
    while i < len(argv):
        token = argv[i]
        if token == "--allow-unisolated-exec":
            allow_unisolated_exec = True
        elif token.startswith("--"):
            name, eq, value = token.partition("=")
            if name not in _VALUE_FLAGS:
                return _usage_error(f"unknown argument: {token}")
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(f"{name} requires a value")
                i += 1
                value = argv[i]
            opts[name] = value
        elif component_id is None:
            component_id = token
        else:
            return _usage_error(f"unknown argument: {token}")
        i += 1

    if component_id is None:
        return _usage_error("missing <component-id>")
    if "--model" not in opts:
        return _usage_error("missing --model")

    seed = 0
    if "--seed" in opts:
        try:
            seed = int(opts["--seed"])
        except ValueError:
            return _usage_error(f"--seed must be an integer: {opts['--seed']}")

    max_attempts = None
    if "--max-attempts" in opts:
        try:
            max_attempts = int(opts["--max-attempts"])
        except ValueError:
            return _usage_error(
                f"--max-attempts must be an integer of at least 1: {opts['--max-attempts']}")
        if max_attempts < 1:
            return _usage_error(
                f"--max-attempts must be an integer of at least 1: {opts['--max-attempts']}")

    mode = opts.get("--mode")
    if mode is not None and mode not in ("single", "agentic"):
        return _usage_error(f"invalid --mode: {mode}")

    fmt = opts.get("--format", "text")
    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format: {fmt}")

    repo_root = Path(opts["--repo-root"]) if "--repo-root" in opts else Path.cwd()

    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else None
    if not slug or not (repo_root / "specs" / "components" / slug / "component.md").is_file():
        return _usage_error(f"unknown component: {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    if toml_path.is_file():
        with open(toml_path, "rb") as handle:
            table = tomllib.load(handle).get("generate", {})
        if "max_attempts" in table:
            if not _valid_max_attempts(table["max_attempts"]):
                return _usage_error(
                    f"{toml_path}: [generate] max_attempts must be an integer of at least 1")
            if max_attempts is None:
                max_attempts = table["max_attempts"]
        if "mode" in table:
            if table["mode"] not in ("single", "agentic"):
                return _usage_error(f"{toml_path}: [generate] mode must be single or agentic")
            if mode is None:
                mode = table["mode"]

    if max_attempts is None:
        max_attempts = 3
    if mode is None:
        mode = "single"

    retry_feedback = opts["--retry-feedback"].split(",") if "--retry-feedback" in opts else None

    result = run_component_gates(
        component_id, repo_root, opts["--model"], seed, None, retry_feedback,
        max_attempts=max_attempts, mode=mode, allow_unisolated_exec=allow_unisolated_exec)

    if fmt == "json":
        print(json.dumps(to_json(result)))
    else:
        _print_text(result)

    if result["block_reason"] in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
