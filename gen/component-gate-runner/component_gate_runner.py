"""Component gate runner: one component's full per-component gauntlet.

`run_component_gates` sequences provenance check, generation, verification,
both compliance scans and provenance writes; `main` is `hotdocs generate`.
"""

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

_VALUE_FLAGS = {
    "--model",
    "--seed",
    "--retry-feedback",
    "--max-attempts",
    "--mode",
    "--repo-root",
    "--format",
}

_MODES = ("single", "agentic")
_FORMATS = ("json", "text")

_BLOCK_REASONS = {
    "generation_failed": "model_call_error",
    "surface_failed": "surface_check_failed",
    "refused": "refused",
}


def _get(obj, name):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    return next(d.parent for d in Path(__file__).resolve().parents if d.name == "gen")


def _load_module(slug, repo_root):
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
    """Loads each dependency afresh per run, on its first call only."""

    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._mods = {}

    def __call__(self, slug):
        if slug not in self._mods:
            self._mods[slug] = _load_module(slug, self._repo_root)
        return self._mods[slug]


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


def _scans(deps, component_id, repo_root):
    license_scan = deps("license-scanner").scan(component_id, repo_root)
    secret_scan = deps("secret-scanner").scan(repo_root)
    return license_scan, secret_scan


def _reverify(deps, component_id, repo_root, model, seed, llm_backend):
    test_author, judge = deps("generation-loop").make_closures(model, seed, repo_root, llm_backend)
    report = deps("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author
    )
    license_scan, secret_scan = _scans(deps, component_id, repo_root)
    return report, license_scan, secret_scan


def _run_sealed(deps, component_id, repo_root, model, seed, llm_backend, sealed_key):
    owners = _get(sealed_key, "owners")
    source_path = _get(sealed_key, "source_path")
    source_hash = _get(sealed_key, "source_hash")
    verifier_version = _get(sealed_key, "verifier_version")
    report, license_scan, secret_scan = _reverify(
        deps, component_id, repo_root, model, seed, llm_backend
    )
    inputs = {
        "component_id": component_id,
        "owners": owners,
        "source_path": source_path,
        "source_hash": source_hash,
        "verifier_version": verifier_version,
        "verification_report": report,
    }
    deps("provenance-writer").write_sealed_provenance(component_id, inputs, repo_root)
    blocked = _get(report, "overall") == "fail"
    return _result(
        component_id,
        blocked=blocked,
        block_reason="verification_failed" if blocked else None,
        verification=report,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


def _verification_block_reason(report):
    failed = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    if failed and all(_get(c, "failure_origin") == "test" for c in failed):
        return "test_authoring_failed"
    return "verification_failed"


def _count_attempt_files(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file())


def run_component_gates(
    component_id, repo_root, model, seed=0, llm_backend=None, retry_feedback=None, *,
    max_attempts=3, mode="single", allow_unisolated_exec=False,
):
    deps = _Deps(repo_root)
    checker = deps("provenance-checker")
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
        report, license_scan, secret_scan = _reverify(
            deps, component_id, repo_root, model, seed, llm_backend
        )
        if (
            _get(report, "overall") == "pass"
            and _get(license_scan, "blocked") is not True
            and _get(secret_scan, "flagged") is not True
        ):
            slug = component_id[len("comp-"):]
            manifest_path = Path(repo_root) / "gen" / slug / ".provenance.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            generation_result = {"files": {}, "spec_bundle_hash": spec_bundle_hash}
            generation_result["model"] = manifest.get("model_pin")
            generation_result["prompt_version"] = manifest.get("prompt_version")
            generation_result["retry_feedback"] = manifest.get("retry_feedback")
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
            deps("provenance-writer").write_provenance(component_id, inputs, repo_root)
            return _result(
                component_id,
                reverified=True,
                verification=report,
                license_scan=license_scan,
                secret_scan=secret_scan,
            )

    bundle = deps("spec-bundle-assembler").assemble(component_id, repo_root=repo_root, mode="cold")

    def on_attempt(attempt, generation_result, verification_report):
        try:
            deps("provenance-tracker").write_attempt_record(
                component_id, generation_result, verification_report, spec_bundle_hash, repo_root
            )
        except Exception:
            pass

    loop = deps("generation-loop").run_attempts(
        component_id, bundle, repo_root, model,
        mode=mode, max_attempts=max_attempts, retry_feedback=retry_feedback,
        seed=seed, llm_backend=llm_backend,
        allow_unisolated_exec=allow_unisolated_exec, on_attempt=on_attempt,
    )
    attempts = _get(loop, "attempts")
    generation_result = _get(loop, "generation_result")
    verification_report = _get(loop, "verification_report")

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
        deps("provenance-writer").write_provenance(component_id, inputs, repo_root)

    if _get(loop, "passed"):
        return _result(
            component_id,
            verification=verification_report,
            attempts=attempts,
            license_scan=license_scan,
            secret_scan=secret_scan,
        )

    outcome = _get(attempts[-1], "outcome")
    if outcome == "verification_failed":
        block_reason = _verification_block_reason(verification_report)
    else:
        block_reason = _BLOCK_REASONS.get(outcome)
    model_call_error = (
        _get(generation_result, "model_call_error")
        if block_reason == "model_call_error"
        else None
    )
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


def to_json(value):
    """Convert any value to plain JSON values (specs/architecture/json-values.md)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {(k if isinstance(k, str) else str(k)): to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((to_json(v) for v in value), key=lambda i: json.dumps(i, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, PurePath):
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


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def _parse_int(text):
    try:
        return int(text)
    except ValueError:
        return None


def _print_text(result):
    print(result["component_id"])
    if result["provenance_hit"]:
        status = "provenance hit"
    elif result["reverified"]:
        status = "reverified"
    elif result["blocked"]:
        status = result["block_reason"]
    else:
        status = "passed"
    print(status)
    for attempt in result["attempts"]:
        print(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    print(f"license_scan blocked: {json.dumps(to_json(_get(license_scan, 'blocked')))}")
    print(f"secret_scan flagged: {json.dumps(to_json(_get(secret_scan, 'flagged')))}")
    mce = result["model_call_error"]
    if mce is not None:
        print(f"model_call_error: {_get(mce, 'category')}: {_get(mce, 'message')}")
    verification = result["verification"]
    if result["block_reason"] == "test_authoring_failed":
        for criterion in _get(verification, "criteria") or []:
            if _get(criterion, "result") == "fail":
                message = _get(_get(criterion, "failure_detail"), "message")
                print(f"{_get(criterion, 'id')}: {message}")
    mutation_error = _get(verification, "mutation_error")
    if mutation_error is not None:
        print(f"mutation_error: {mutation_error}")
    if _get(license_scan, "evaluated") is False:
        print(f"license_scan not evaluated: {_get(license_scan, 'reason')}")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv or argv[0] != "generate":
        return _usage_error("first word must be 'generate'")

    tokens = argv[1:]
    opts = {}
    positionals = []
    allow_unisolated_exec = False
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, eq, value = token.partition("=")
        if name in _VALUE_FLAGS:
            if not eq:
                if i + 1 >= len(tokens):
                    return _usage_error(f"{name} requires a value")
                i += 1
                value = tokens[i]
            opts[name] = value
        elif token == "--allow-unisolated-exec":
            allow_unisolated_exec = True
        elif token.startswith("-") or positionals:
            return _usage_error(f"unknown argument: {token}")
        else:
            positionals.append(token)
        i += 1

    if not positionals:
        return _usage_error("missing <component-id>")
    component_id = positionals[0]
    if "--model" not in opts:
        return _usage_error("missing --model")
    model = opts["--model"]

    output_format = opts.get("--format", "text")
    if output_format not in _FORMATS:
        return _usage_error(f"invalid --format: {output_format}")

    if "--mode" in opts and opts["--mode"] not in _MODES:
        return _usage_error(f"invalid --mode: {opts['--mode']}")

    seed = 0
    if "--seed" in opts:
        seed = _parse_int(opts["--seed"])
        if seed is None:
            return _usage_error(f"--seed must be an integer: {opts['--seed']}")

    if "--max-attempts" in opts:
        flag_attempts = _parse_int(opts["--max-attempts"])
        if flag_attempts is None or flag_attempts < 1:
            return _usage_error(
                f"--max-attempts must be an integer of at least 1: {opts['--max-attempts']}"
            )

    repo_root = Path(opts["--repo-root"]) if "--repo-root" in opts else Path.cwd()

    component_md = (
        repo_root / "specs" / "components" / component_id[len("comp-"):] / "component.md"
    )
    if not component_id.startswith("comp-") or not component_md.is_file():
        return _usage_error(f"unknown component: {component_id}")

    max_attempts = 3
    mode = "single"
    toml_path = repo_root / "hotdocs.toml"
    if toml_path.is_file():
        with open(toml_path, "rb") as handle:
            config = tomllib.load(handle)
        table = config.get("generate")
        if isinstance(table, dict):
            if "max_attempts" in table:
                file_attempts = table["max_attempts"]
                if (
                    not isinstance(file_attempts, int)
                    or isinstance(file_attempts, bool)
                    or file_attempts < 1
                ):
                    return _usage_error(
                        f"{toml_path}: [generate] max_attempts must be an integer of at least 1"
                    )
                max_attempts = file_attempts
            if "mode" in table:
                file_mode = table["mode"]
                if not isinstance(file_mode, str) or file_mode not in _MODES:
                    return _usage_error(
                        f"{toml_path}: [generate] mode must be 'single' or 'agentic'"
                    )
                mode = file_mode

    if "--max-attempts" in opts:
        max_attempts = flag_attempts
    if "--mode" in opts:
        mode = opts["--mode"]

    retry_feedback = (
        opts["--retry-feedback"].split(",") if "--retry-feedback" in opts else None
    )

    result = run_component_gates(
        component_id, repo_root, model, seed, None, retry_feedback,
        max_attempts=max_attempts, mode=mode,
        allow_unisolated_exec=allow_unisolated_exec,
    )

    if output_format == "json":
        print(json.dumps(to_json(result), indent=2))
    else:
        _print_text(result)

    if result["block_reason"] in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
