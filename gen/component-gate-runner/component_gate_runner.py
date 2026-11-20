"""Component Gate Runner: one component's full per-component gauntlet.

Provenance check, generation on a miss, verification, both compliance
scans and the provenance write, producing one ``ComponentPipelineResult``.
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

__all__ = ["run_component_gates", "main"]

_LOAD_COUNTER = itertools.count()

USAGE = (
    "usage: hotdocs generate <component-id> --model=<model-id> [--seed=<n>] "
    "[--retry-feedback=<R-id>,...] [--max-attempts=<n>] [--mode=single|agentic] "
    "[--allow-unisolated-exec] [--repo-root=<dir>] [--format=json|text]"
)

_VALUE_FLAGS = (
    "model",
    "seed",
    "retry-feedback",
    "max-attempts",
    "mode",
    "repo-root",
    "format",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    here = Path(__file__).resolve()
    return next(d.parent for d in here.parents if d.name == "gen")


def _load_dependency(slug, repo_root):
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
        self.repo_root = repo_root
        self.modules = {}

    def __call__(self, slug):
        if slug not in self.modules:
            self.modules[slug] = _load_dependency(slug, self.repo_root)
        return self.modules[slug]


def _result(
    component_id,
    *,
    provenance_hit=False,
    reverified=False,
    blocked=False,
    block_reason=None,
    model_call_error=None,
    verification=None,
    attempts=None,
    license_scan=None,
    secret_scan=None,
):
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


def _closures_and_verify(deps, component_id, repo_root, model, seed, llm_backend):
    test_author, judge = deps("generation-loop").make_closures(
        model, seed, repo_root, llm_backend
    )
    return deps("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author
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
    return len([p for p in directory.iterdir() if p.is_file()])


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def run_component_gates(
    component_id,
    repo_root,
    model,
    seed=0,
    llm_backend=None,
    retry_feedback=None,
    *,
    max_attempts=3,
    mode="single",
    allow_unisolated_exec=False,
):
    deps = _Deps(repo_root)
    checker = deps("provenance-checker")
    sealed_key = checker.current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(
            deps, component_id, repo_root, model, seed, llm_backend, sealed_key
        )

    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = checker.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root
    )
    check_report = _get(check, "verification_report")
    check_license = _get(check, "license_scan")
    if (
        _get(check, "hit")
        and _get(check_report, "overall") == "pass"
        and _get(check_license, "blocked") is not True
    ):
        return _result(
            component_id,
            provenance_hit=True,
            verification=check_report,
            license_scan=check_license,
            secret_scan=_get(check, "secret_scan"),
        )

    if _get(check, "reason") == "environment differs":
        report = _closures_and_verify(
            deps, component_id, repo_root, model, seed, llm_backend
        )
        license_scan, secret_scan = _scans(deps, component_id, repo_root)
        if (
            _get(report, "overall") == "pass"
            and _get(license_scan, "blocked") is not True
            and _get(secret_scan, "flagged") is not True
        ):
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
            for field, value in manifest.get("generation", {}).items():
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

    bundle = deps("spec-bundle-assembler").assemble(
        component_id, repo_root=repo_root, mode="cold"
    )

    def on_attempt(attempt, generation_result, verification_report):
        try:
            deps("provenance-tracker").write_attempt_record(
                component_id,
                generation_result,
                verification_report,
                spec_bundle_hash,
                repo_root,
            )
        except Exception:
            pass

    loop_result = deps("generation-loop").run_attempts(
        component_id,
        bundle,
        repo_root,
        model,
        mode=mode,
        max_attempts=max_attempts,
        retry_feedback=retry_feedback,
        seed=seed,
        llm_backend=llm_backend,
        allow_unisolated_exec=allow_unisolated_exec,
        on_attempt=on_attempt,
    )
    attempts = _get(loop_result, "attempts")
    generation_result = _get(loop_result, "generation_result")
    verification_report = _get(loop_result, "verification_report")

    license_scan, secret_scan = _scans(deps, component_id, repo_root)

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
        else:
            block_reason = _verification_block_reason(verification_report)

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

    return _result(
        component_id,
        blocked=blocked,
        block_reason=block_reason,
        model_call_error=model_call_error,
        verification=verification_report,
        attempts=attempts,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


def _run_sealed(deps, component_id, repo_root, model, seed, llm_backend, sealed_key):
    report = _closures_and_verify(deps, component_id, repo_root, model, seed, llm_backend)
    license_scan, secret_scan = _scans(deps, component_id, repo_root)
    inputs = {
        "component_id": component_id,
        "owners": _get(sealed_key, "owners"),
        "source_path": _get(sealed_key, "source_path"),
        "source_hash": _get(sealed_key, "source_hash"),
        "verifier_version": _get(sealed_key, "verifier_version"),
        "verification_report": report,
    }
    deps("provenance-writer").write_sealed_provenance(component_id, inputs, repo_root)
    failed = _get(report, "overall") == "fail"
    return _result(
        component_id,
        blocked=failed,
        block_reason="verification_failed" if failed else None,
        verification=report,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


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
            (k if isinstance(k, str) else str(k)): to_json(v) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (to_json(v) for v in value), key=lambda i: json.dumps(i, sort_keys=True)
        )
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
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
# CLI
# ---------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _parse(argv):
    if not argv or argv[0] != "generate":
        raise _UsageError("first word must be 'generate'")
    values = {}
    allow_unisolated = False
    positionals = []
    tokens = argv[1:]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "--allow-unisolated-exec":
            allow_unisolated = True
        elif token.startswith("--"):
            name, eq, value = token[2:].partition("=")
            if name not in _VALUE_FLAGS:
                raise _UsageError(f"unknown argument: {token}")
            if not eq:
                if i + 1 >= len(tokens):
                    raise _UsageError(f"--{name} given with no value")
                i += 1
                value = tokens[i]
            values[name] = value
        else:
            positionals.append(token)
        i += 1
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument: {positionals[1]}")
    return positionals, values, allow_unisolated


def _read_generate_table(repo_root):
    path = repo_root / "hotdocs.toml"
    if not path.is_file():
        return path, {}
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return path, data.get("generate", {})


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        positionals, values, allow_unisolated = _parse(list(argv))
        if not positionals:
            raise _UsageError("missing <component-id>")
        component_id = positionals[0]
        if "model" not in values:
            raise _UsageError("missing --model")
        model = values["model"]
        seed_text = values.get("seed", "0")
        try:
            seed = int(seed_text)
        except ValueError:
            raise _UsageError(f"--seed must be an integer, got {seed_text!r}")
        output_format = values.get("format", "text")
        if output_format not in ("json", "text"):
            raise _UsageError(f"invalid --format: {output_format}")
        repo_root = Path(values.get("repo-root", "."))

        toml_path, table = _read_generate_table(repo_root)
        file_max = table.get("max_attempts")
        if "max_attempts" in table and (
            not isinstance(file_max, int) or isinstance(file_max, bool) or file_max < 1
        ):
            raise _UsageError(
                f"invalid [generate] max_attempts in {toml_path}: {file_max!r}"
            )
        file_mode = table.get("mode")
        if "mode" in table and file_mode not in ("single", "agentic"):
            raise _UsageError(f"invalid [generate] mode in {toml_path}: {file_mode!r}")

        if "max-attempts" in values:
            text = values["max-attempts"]
            try:
                max_attempts = int(text)
            except ValueError:
                raise _UsageError(f"--max-attempts must be an integer, got {text!r}")
            if max_attempts < 1:
                raise _UsageError("--max-attempts must be at least 1")
        else:
            max_attempts = table.get("max_attempts", 3)

        mode = values.get("mode", table.get("mode", "single"))
        if mode not in ("single", "agentic"):
            raise _UsageError(f"invalid --mode: {mode}")

        retry_feedback = (
            values["retry-feedback"].split(",") if "retry-feedback" in values else None
        )

        slug = component_id[len("comp-"):]
        if not component_id.startswith("comp-") or not (
            repo_root / "specs" / "components" / slug / "component.md"
        ).is_file():
            raise _UsageError(f"unknown component: {component_id}")
    except _UsageError as exc:
        return _usage_error(str(exc))

    result = run_component_gates(
        component_id,
        repo_root,
        model,
        seed,
        retry_feedback=retry_feedback,
        max_attempts=max_attempts,
        mode=mode,
        allow_unisolated_exec=allow_unisolated,
    )

    if output_format == "json":
        print(json.dumps(to_json(result)))
    else:
        _print_text(result)

    if result["block_reason"] in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0


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
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    print(f"license_scan blocked: {json.dumps(to_json(_get(license_scan, 'blocked')))}")
    print(f"secret_scan flagged: {json.dumps(to_json(_get(secret_scan, 'flagged')))}")
    error = result["model_call_error"]
    if error:
        print(f"model_call_error: {_get(error, 'category')}: {_get(error, 'message')}")
    verification = result["verification"]
    if result["block_reason"] == "test_authoring_failed":
        for criterion in _get(verification, "criteria") or []:
            if _get(criterion, "result") == "fail":
                message = _get(_get(criterion, "failure_detail"), "message")
                print(f"{_get(criterion, 'id')}: {message}")
    mutation_error = _get(verification, "mutation_error")
    if mutation_error:
        print(f"mutation_error: {mutation_error}")
    if _get(license_scan, "evaluated") is False:
        print(f"license_scan not evaluated: {_get(license_scan, 'reason')}")
