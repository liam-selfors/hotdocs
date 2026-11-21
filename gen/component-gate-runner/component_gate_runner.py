"""Component gate runner: one component's full per-component gauntlet."""

import dataclasses
import enum
import importlib.util
import itertools
import json
import math
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path, PurePath

_LOAD_COUNTER = itertools.count()

_USAGE = (
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

_OUTCOME_REASONS = {
    "generation_failed": "model_call_error",
    "surface_failed": "surface_check_failed",
    "refused": "refused",
}


def _get(obj, key):
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_module(repo_root, slug):
    module = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module}.py"
    name = f"_component_gate_runner_dep_{module}_{next(_LOAD_COUNTER)}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Deps:
    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._loaded = {}

    def get(self, slug):
        if slug not in self._loaded:
            self._loaded[slug] = _load_module(self._repo_root, slug)
        return self._loaded[slug]


def _result(component_id, *, provenance_hit=False, reverified=False, blocked=False,
            block_reason=None, model_call_error=None, verification=None,
            attempts=None, license_scan=None, secret_scan=None):
    return {
        "component_id": component_id,
        "provenance_hit": provenance_hit,
        "reverified": reverified,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": model_call_error,
        "verification": verification,
        "attempts": [] if attempts is None else attempts,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _verify_committed(deps, component_id, repo_root, model, seed, llm_backend):
    loop = deps.get("generation-loop")
    test_author, judge = loop.make_closures(model, seed, repo_root, llm_backend)
    verifier = deps.get("verifier-orchestrator")
    report = verifier.verify(component_id, repo_root, judge=judge, test_author=test_author)
    license_scan, secret_scan = _scans(deps, component_id, repo_root)
    return report, license_scan, secret_scan


def _scans(deps, component_id, repo_root):
    license_scan = deps.get("license-scanner").scan(component_id, repo_root)
    secret_scan = deps.get("secret-scanner").scan(repo_root)
    return license_scan, secret_scan


def _count_attempt_files(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return len(list(directory.iterdir()))


def _is_test_authoring_failure(report):
    failed = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    return bool(failed) and all(_get(c, "failure_origin") == "test" for c in failed)


def _run_sealed(deps, component_id, repo_root, model, seed, llm_backend, sealed_key):
    report, license_scan, secret_scan = _verify_committed(
        deps, component_id, repo_root, model, seed, llm_backend
    )
    inputs = {
        "component_id": component_id,
        "owners": _get(sealed_key, "owners"),
        "source_path": _get(sealed_key, "source_path"),
        "source_hash": _get(sealed_key, "source_hash"),
        "verifier_version": _get(sealed_key, "verifier_version"),
        "verification_report": report,
    }
    deps.get("provenance-writer").write_sealed_provenance(component_id, inputs, repo_root)
    blocked = _get(report, "overall") == "fail"
    return _result(
        component_id,
        blocked=blocked,
        block_reason="verification_failed" if blocked else None,
        verification=report,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


def _reverify(deps, component_id, repo_root, model, seed, llm_backend,
              spec_bundle_hash, gate_versions):
    report, license_scan, secret_scan = _verify_committed(
        deps, component_id, repo_root, model, seed, llm_backend
    )
    if not (
        _get(report, "overall") == "pass"
        and _get(license_scan, "blocked") is not True
        and _get(secret_scan, "flagged") is not True
    ):
        return None
    slug = component_id[len("comp-"):]
    manifest_path = Path(repo_root) / "gen" / slug / ".provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generation_result = {
        "files": {},
        "spec_bundle_hash": spec_bundle_hash,
        "model": manifest.get("model_pin"),
        "prompt_version": manifest.get("prompt_version"),
        "retry_feedback": manifest.get("retry_feedback"),
    }
    for field, value in (manifest.get("generation") or {}).items():
        if field != "generator_version":
            generation_result[field] = value
    inputs = {
        "component_id": component_id,
        "generation_result": generation_result,
        "verification_report": report,
        "license_scan_result": license_scan,
        "secret_scan_result": secret_scan,
        "provenance_hit": False,
        "attempts": manifest.get("attempts"),
        "attempt_history": manifest.get("attempt_history"),
        "gate_versions": gate_versions,
    }
    deps.get("provenance-writer").write_provenance(component_id, inputs, repo_root)
    return _result(
        component_id,
        reverified=True,
        verification=report,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


def run_component_gates(
    component_id, repo_root, model, seed=0, llm_backend=None, retry_feedback=None, *,
    max_attempts=3, mode="single", allow_unisolated_exec=False,
):
    deps = _Deps(repo_root)
    checker = deps.get("provenance-checker")
    sealed_key = checker.current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(deps, component_id, repo_root, model, seed, llm_backend, sealed_key)

    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = checker.check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)
    hit_report = _get(check, "verification_report")
    hit_license = _get(check, "license_scan")
    if (
        _get(check, "hit")
        and _get(hit_report, "overall") == "pass"
        and _get(hit_license, "blocked") is not True
    ):
        return _result(
            component_id,
            provenance_hit=True,
            verification=hit_report,
            license_scan=hit_license,
            secret_scan=_get(check, "secret_scan"),
        )

    if _get(check, "reason") == "environment differs":
        reverified = _reverify(
            deps, component_id, repo_root, model, seed, llm_backend,
            spec_bundle_hash, gate_versions,
        )
        if reverified is not None:
            return reverified

    bundle = deps.get("spec-bundle-assembler").assemble(
        component_id, repo_root=repo_root, mode="cold"
    )

    def on_attempt(attempt, generation_result, verification_report):
        try:
            deps.get("provenance-tracker").write_attempt_record(
                component_id, generation_result, verification_report,
                spec_bundle_hash, repo_root,
            )
        except Exception:
            pass

    loop_result = deps.get("generation-loop").run_attempts(
        component_id, bundle, repo_root, model,
        mode=mode, max_attempts=max_attempts, retry_feedback=retry_feedback,
        seed=seed, llm_backend=llm_backend,
        allow_unisolated_exec=allow_unisolated_exec, on_attempt=on_attempt,
    )
    attempts = _get(loop_result, "attempts")
    generation_result = _get(loop_result, "generation_result")
    verification_report = _get(loop_result, "verification_report")

    license_scan, secret_scan = _scans(deps, component_id, repo_root)

    if _get(generation_result, "files"):
        inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": license_scan,
            "secret_scan_result": secret_scan,
            "provenance_hit": False,
            "attempts": _count_attempt_files(repo_root, component_id),
            "attempt_history": attempts,
            "gate_versions": gate_versions,
        }
        deps.get("provenance-writer").write_provenance(component_id, inputs, repo_root)

    if _get(loop_result, "passed"):
        return _result(
            component_id,
            verification=verification_report,
            attempts=attempts,
            license_scan=license_scan,
            secret_scan=secret_scan,
        )

    outcome = _get(attempts[-1], "outcome")
    if outcome == "verification_failed":
        if _is_test_authoring_failure(verification_report):
            block_reason = "test_authoring_failed"
        else:
            block_reason = "verification_failed"
    else:
        block_reason = _OUTCOME_REASONS.get(outcome)
    model_call_error = None
    if block_reason == "model_call_error":
        model_call_error = _get(generation_result, "model_call_error")
    return _result(
        component_id,
        blocked=True,
        block_reason=block_reason,
        model_call_error=model_call_error,
        verification=verification_report,
        attempts=attempts,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


def _to_json(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {
            (k if isinstance(k, str) else str(k)): _to_json(v) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [_to_json(v) for v in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return _to_json(value.value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _to_json(to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if hasattr(value, "__dict__"):
        return {
            k: _to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


class _UsageError(Exception):
    pass


def _parse(argv):
    if not argv or argv[0] != "generate":
        raise _UsageError("first word must be 'generate'")
    opts = {}
    positionals = []
    allow = False
    i = 1
    while i < len(argv):
        tok = argv[i]
        name, eq, val = tok.partition("=")
        if name in _VALUE_FLAGS:
            if eq:
                opts[name] = val
            elif i + 1 >= len(argv):
                raise _UsageError(f"{name} given with no value")
            else:
                i += 1
                opts[name] = argv[i]
        elif tok == "--allow-unisolated-exec":
            allow = True
        elif tok.startswith("-") or positionals:
            raise _UsageError(f"unknown argument: {tok}")
        else:
            positionals.append(tok)
        i += 1
    if not positionals:
        raise _UsageError("missing <component-id>")
    if "--model" not in opts:
        raise _UsageError("missing --model")
    return positionals[0], opts, allow


def _parse_int(text, flag):
    try:
        return int(text)
    except ValueError:
        raise _UsageError(f"{flag} must be an integer: {text}")


def _resolve(argv):
    component_id, opts, allow = _parse(argv)
    seed = _parse_int(opts.get("--seed", "0"), "--seed")
    max_attempts = None
    if "--max-attempts" in opts:
        max_attempts = _parse_int(opts["--max-attempts"], "--max-attempts")
        if max_attempts < 1:
            raise _UsageError("--max-attempts must be at least 1")
    fmt = opts.get("--format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")
    mode = opts.get("--mode")
    if mode is not None and mode not in ("single", "agentic"):
        raise _UsageError(f"invalid --mode: {mode}")
    repo_root = Path(opts["--repo-root"]) if "--repo-root" in opts else Path.cwd()
    slug = component_id[len("comp-"):]
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_id.startswith("comp-") or not component_md.is_file():
        raise _UsageError(f"unknown component: {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    table = {}
    if toml_path.is_file():
        with open(toml_path, "rb") as fh:
            table = tomllib.load(fh).get("generate", {})
    if "max_attempts" in table:
        value = table["max_attempts"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise _UsageError(f"invalid [generate] max_attempts in {toml_path}")
        if max_attempts is None:
            max_attempts = value
    if "mode" in table:
        value = table["mode"]
        if value not in ("single", "agentic"):
            raise _UsageError(f"invalid [generate] mode in {toml_path}")
        if mode is None:
            mode = value

    retry_feedback = None
    if "--retry-feedback" in opts:
        retry_feedback = opts["--retry-feedback"].split(",")
    return {
        "component_id": component_id,
        "repo_root": repo_root,
        "model": opts["--model"],
        "seed": seed,
        "retry_feedback": retry_feedback,
        "max_attempts": 3 if max_attempts is None else max_attempts,
        "mode": "single" if mode is None else mode,
        "allow_unisolated_exec": allow,
        "format": fmt,
    }


def _text_lines(result):
    lines = [str(result["component_id"])]
    if result["provenance_hit"]:
        lines.append("provenance hit")
    elif result["reverified"]:
        lines.append("reverified")
    else:
        lines.append(result["block_reason"] or "passed")
    for attempt in result["attempts"]:
        lines.append(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    lines.append(f"license_scan blocked: {json.dumps(_to_json(_get(license_scan, 'blocked')))}")
    lines.append(f"secret_scan flagged: {json.dumps(_to_json(_get(secret_scan, 'flagged')))}")
    error = result["model_call_error"]
    if error:
        lines.append(f"model_call_error: {_get(error, 'category')}: {_get(error, 'message')}")
    verification = result["verification"]
    if result["block_reason"] == "test_authoring_failed":
        for criterion in _get(verification, "criteria") or []:
            if _get(criterion, "result") == "fail":
                message = _get(_get(criterion, "failure_detail"), "message")
                lines.append(f"{_get(criterion, 'id')}: {message}")
    mutation_error = _get(verification, "mutation_error")
    if mutation_error:
        if not isinstance(mutation_error, str):
            mutation_error = _get(mutation_error, "message")
        lines.append(f"mutation_error: {mutation_error}")
    if _get(license_scan, "evaluated") is False:
        lines.append(f"license_scan not evaluated: {_get(license_scan, 'reason')}")
    return lines


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    try:
        args = _resolve(argv)
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    result = run_component_gates(
        args["component_id"], args["repo_root"], args["model"], args["seed"],
        None, args["retry_feedback"],
        max_attempts=args["max_attempts"], mode=args["mode"],
        allow_unisolated_exec=args["allow_unisolated_exec"],
    )
    if args["format"] == "json":
        print(json.dumps(_to_json(result)))
    else:
        print("\n".join(_text_lines(result)))
    if result["block_reason"] in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
