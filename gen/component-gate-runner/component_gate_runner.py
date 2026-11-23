"""Component Gate Runner: runs one component through its gauntlet.

Provenance check, generation on a miss, verification, compliance scanning
and provenance write, giving one ``ComponentPipelineResult`` dict.
"""

from __future__ import annotations

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

_MODES = ("single", "agentic")
_FORMATS = ("json", "text")

_LOAD_COUNTER = itertools.count()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve().parent
    for directory in (here, *here.parents):
        if directory.name == "gen":
            return directory.parent
    return here.parent


def _load_module(slug: str, repo_root):
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
    """Per-call, lazy dependency loader: each module loads on first use."""

    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._modules = {}

    def __call__(self, slug: str):
        if slug not in self._modules:
            self._modules[slug] = _load_module(slug, self._repo_root)
        return self._modules[slug]


def _result(
    component_id,
    *,
    provenance_hit=False,
    reverified=False,
    blocked=False,
    block_reason=None,
    model_call_error=None,
    surface_report=None,
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
        "surface_report": surface_report,
        "verification": verification,
        "attempts": [] if attempts is None else attempts,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _is_test_authoring_failure(report) -> bool:
    failed = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    return bool(failed) and all(_get(c, "failure_origin") == "test" for c in failed)


def _count_attempt_files(repo_root, component_id) -> int:
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return sum(1 for entry in directory.iterdir() if entry.is_file())


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def run_component_gates(
    component_id: str,
    repo_root: Path,
    model: str,
    seed: int = 0,
    llm_backend=None,
    retry_feedback: list[str] | None = None,
    *,
    max_attempts: int = 3,
    mode: str = "single",
    allow_unisolated_exec: bool = False,
):
    deps = _Deps(repo_root)

    sealed_key = deps("provenance-checker").current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(component_id, repo_root, model, seed, llm_backend, sealed_key, deps)

    checker = deps("provenance-checker")
    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = checker.check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)

    if (
        _get(check, "hit")
        and _get(_get(check, "verification_report"), "overall") == "pass"
        and _get(_get(check, "license_scan"), "blocked") is not True
    ):
        return _result(
            component_id,
            provenance_hit=True,
            verification=_get(check, "verification_report"),
            license_scan=_get(check, "license_scan"),
            secret_scan=_get(check, "secret_scan"),
        )

    if _get(check, "reason") == "environment differs":
        test_author, judge = deps("generation-loop").make_closures(
            model, seed, repo_root, llm_backend
        )
        report = deps("verifier-orchestrator").verify(
            component_id, repo_root, judge=judge, test_author=test_author
        )
        license_scan = deps("license-scanner").scan(component_id, repo_root)
        secret_scan = deps("secret-scanner").scan(repo_root)
        if (
            _get(report, "overall") == "pass"
            and _get(license_scan, "blocked") is not True
            and _get(secret_scan, "flagged") is not True
        ):
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

    license_scan = deps("license-scanner").scan(component_id, repo_root)
    secret_scan = deps("secret-scanner").scan(repo_root)

    attempts = _get(loop_result, "attempts")
    generation_result = _get(loop_result, "generation_result")
    verification_report = _get(loop_result, "verification_report")
    surface_report = _get(loop_result, "surface_report")

    if _get(generation_result, "files") and verification_report is not None:
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
        component_id,
        blocked=blocked,
        block_reason=block_reason,
        model_call_error=model_call_error,
        surface_report=surface_report,
        verification=verification_report,
        attempts=attempts,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


def _run_sealed(component_id, repo_root, model, seed, llm_backend, sealed_key, deps):
    owners = _get(sealed_key, "owners")
    source_path = _get(sealed_key, "source_path")
    source_hash = _get(sealed_key, "source_hash")
    verifier_version = _get(sealed_key, "verifier_version")

    test_author, judge = deps("generation-loop").make_closures(model, seed, repo_root, llm_backend)
    report = deps("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author
    )
    license_scan = deps("license-scanner").scan(component_id, repo_root)
    secret_scan = deps("secret-scanner").scan(repo_root)

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
        return [to_json(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (to_json(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse_args(argv):
    if not argv or argv[0] != "generate":
        raise _UsageError("expected first word 'generate'")
    opts = {}
    positionals = []
    allow_unisolated_exec = False
    i = 1
    while i < len(argv):
        token = argv[i]
        if token.startswith("-"):
            name, eq, value = token.partition("=")
            if name == "--allow-unisolated-exec" and not eq:
                allow_unisolated_exec = True
            elif name in _VALUE_FLAGS:
                if not eq:
                    if i + 1 >= len(argv):
                        raise _UsageError(f"{name} requires a value")
                    i += 1
                    value = argv[i]
                opts[name] = value
            else:
                raise _UsageError(f"unknown argument: {token}")
        else:
            positionals.append(token)
        i += 1

    if not positionals:
        raise _UsageError("missing <component-id>")
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument: {positionals[1]}")
    component_id = positionals[0]

    if "--model" not in opts:
        raise _UsageError("missing --model")
    model = opts["--model"]

    seed = 0
    if "--seed" in opts:
        try:
            seed = int(opts["--seed"])
        except ValueError:
            raise _UsageError(f"--seed must be an integer: {opts['--seed']}") from None

    max_attempts = None
    if "--max-attempts" in opts:
        try:
            max_attempts = int(opts["--max-attempts"])
        except ValueError:
            raise _UsageError(
                f"--max-attempts must be an integer of at least 1: {opts['--max-attempts']}"
            ) from None
        if max_attempts < 1:
            raise _UsageError(
                f"--max-attempts must be an integer of at least 1: {opts['--max-attempts']}"
            )

    fmt = opts.get("--format", "text")
    if fmt not in _FORMATS:
        raise _UsageError(f"invalid --format: {fmt}")

    mode = opts.get("--mode")
    if mode is not None and mode not in _MODES:
        raise _UsageError(f"invalid --mode: {mode}")

    repo_root = Path(opts["--repo-root"]) if "--repo-root" in opts else Path.cwd()

    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else None
    if not slug or not (repo_root / "specs" / "components" / slug / "component.md").is_file():
        raise _UsageError(f"unknown component: {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    if toml_path.is_file():
        with open(toml_path, "rb") as handle:
            table = tomllib.load(handle).get("generate", {})
        if "max_attempts" in table:
            file_value = table["max_attempts"]
            if isinstance(file_value, bool) or not isinstance(file_value, int) or file_value < 1:
                raise _UsageError(
                    f"invalid [generate] max_attempts in {toml_path}: {file_value!r}"
                )
            if max_attempts is None:
                max_attempts = file_value
        if "mode" in table:
            file_value = table["mode"]
            if file_value not in _MODES:
                raise _UsageError(f"invalid [generate] mode in {toml_path}: {file_value!r}")
            if mode is None:
                mode = file_value

    retry_feedback = (
        opts["--retry-feedback"].split(",") if "--retry-feedback" in opts else None
    )

    return {
        "component_id": component_id,
        "repo_root": repo_root,
        "model": model,
        "seed": seed,
        "retry_feedback": retry_feedback,
        "max_attempts": 3 if max_attempts is None else max_attempts,
        "mode": "single" if mode is None else mode,
        "allow_unisolated_exec": allow_unisolated_exec,
        "format": fmt,
    }


def _flag_text(value) -> str:
    return json.dumps(to_json(value))


def _print_text(result) -> None:
    lines = [str(_get(result, "component_id"))]
    block_reason = _get(result, "block_reason")
    if _get(result, "provenance_hit"):
        lines.append("provenance hit")
    elif _get(result, "reverified"):
        lines.append("reverified")
    else:
        lines.append(block_reason if block_reason else "passed")

    for attempt in _get(result, "attempts") or []:
        lines.append(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")

    license_scan = _get(result, "license_scan")
    secret_scan = _get(result, "secret_scan")
    lines.append(f"license_scan blocked: {_flag_text(_get(license_scan, 'blocked'))}")
    lines.append(f"secret_scan flagged: {_flag_text(_get(secret_scan, 'flagged'))}")

    model_call_error = _get(result, "model_call_error")
    if model_call_error:
        lines.append(
            f"model_call_error: {_get(model_call_error, 'category')}: "
            f"{_get(model_call_error, 'message')}"
        )

    if block_reason == "surface_check_failed":
        for finding in _get(_get(result, "surface_report"), "findings") or []:
            lines.append(f"surface: {_get(finding, 'message')}")

    verification = _get(result, "verification")
    if block_reason == "test_authoring_failed":
        for criterion in _get(verification, "criteria") or []:
            if _get(criterion, "result") == "fail":
                detail = _get(criterion, "failure_detail")
                lines.append(f"{_get(criterion, 'id')}: {_get(detail, 'message')}")

    mutation_error = _get(verification, "mutation_error")
    if mutation_error:
        message = mutation_error if isinstance(mutation_error, str) else _get(mutation_error, "message")
        lines.append(f"mutation_error: {message}")

    if _get(license_scan, "evaluated") is False:
        lines.append(f"license_scan not evaluated: {_get(license_scan, 'reason')}")

    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = _parse_args(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    result = run_component_gates(
        args["component_id"],
        args["repo_root"],
        args["model"],
        args["seed"],
        None,
        args["retry_feedback"],
        max_attempts=args["max_attempts"],
        mode=args["mode"],
        allow_unisolated_exec=args["allow_unisolated_exec"],
    )

    if args["format"] == "json":
        print(json.dumps(to_json(result)))
    else:
        _print_text(result)

    if _get(result, "block_reason") in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
