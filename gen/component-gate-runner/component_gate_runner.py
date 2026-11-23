"""Component Gate Runner: runs one component through its gauntlet.

`run_component_gates` performs the provenance check, generation on a miss,
verification, compliance scanning and provenance write, giving one
`ComponentPipelineResult` dict. `main` implements `hotdocs generate`.
"""

from __future__ import annotations

import collections.abc
import dataclasses
import enum
import importlib.util
import itertools
import json
import math
import pathlib
import sys
import tomllib
from pathlib import Path

USAGE = (
    "usage: hotdocs generate <component-id> --model=<model-id> [--seed=<n>] "
    "[--retry-feedback=<R-id>,...] [--max-attempts=<n>] [--mode=single|agentic] "
    "[--allow-unisolated-exec] [--repo-root=<dir>] [--format=json|text]"
)

_LOAD_COUNTER = itertools.count()


# ---------------------------------------------------------------------------
# Helpers


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, collections.abc.Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load(slug: str, repo_root):
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
    """Loads each dependency afresh per run, only when first used."""

    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._modules = {}

    def __call__(self, slug):
        if slug not in self._modules:
            self._modules[slug] = _load(slug, self._repo_root)
        return self._modules[slug]


def _result(component_id, **fields):
    result = {
        "component_id": component_id,
        "provenance_hit": False,
        "reverified": False,
        "blocked": False,
        "block_reason": None,
        "model_call_error": None,
        "surface_report": None,
        "verification": None,
        "attempts": [],
        "license_scan": None,
        "secret_scan": None,
    }
    result.update(fields)
    return result


def _count_attempt_files(component_id, repo_root) -> int:
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file())


def _scans(deps, component_id, repo_root):
    license_scan = deps("license-scanner").scan(component_id, repo_root)
    secret_scan = deps("secret-scanner").scan(repo_root)
    return license_scan, secret_scan


def _block_reason(outcome, verification_report):
    if outcome == "generation_failed":
        return "model_call_error"
    if outcome == "surface_failed":
        return "surface_check_failed"
    if outcome == "refused":
        return "refused"
    criteria = _get(verification_report, "criteria") or []
    failed = [c for c in criteria if _get(c, "result") == "fail"]
    if failed and all(_get(c, "failure_origin") == "test" for c in failed):
        return "test_authoring_failed"
    return "verification_failed"


# ---------------------------------------------------------------------------
# Library


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
        return _run_sealed(
            deps, component_id, repo_root, model, seed, llm_backend, sealed_key
        )

    checker = deps("provenance-checker")
    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = checker.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root
    )

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
            for name, value in manifest.get("generation", {}).items():
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

    loop = deps("generation-loop").run_attempts(
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
    attempts = _get(loop, "attempts")
    generation_result = _get(loop, "generation_result")
    verification_report = _get(loop, "verification_report")
    surface_report = _get(loop, "surface_report")

    license_scan, secret_scan = _scans(deps, component_id, repo_root)

    if _get(generation_result, "files") and verification_report is not None:
        inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": license_scan,
            "secret_scan_result": secret_scan,
            "provenance_hit": False,
            "attempts": _count_attempt_files(component_id, repo_root),
            "attempt_history": attempts,
            "gate_versions": gate_versions,
        }
        deps("provenance-writer").write_provenance(component_id, inputs, repo_root)

    blocked = False
    block_reason = None
    model_call_error = None
    if not _get(loop, "passed"):
        blocked = True
        block_reason = _block_reason(
            _get(attempts[-1], "outcome"), verification_report
        )
        if block_reason == "model_call_error":
            model_call_error = _get(generation_result, "model_call_error")

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


def _run_sealed(deps, component_id, repo_root, model, seed, llm_backend, sealed_key):
    owners = _get(sealed_key, "owners")
    source_path = _get(sealed_key, "source_path")
    source_hash = _get(sealed_key, "source_hash")
    verifier_version = _get(sealed_key, "verifier_version")

    test_author, judge = deps("generation-loop").make_closures(
        model, seed, repo_root, llm_backend
    )
    report = deps("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author
    )
    license_scan, secret_scan = _scans(deps, component_id, repo_root)

    inputs = {
        "component_id": component_id,
        "owners": owners,
        "source_path": source_path,
        "source_hash": source_hash,
        "verifier_version": verifier_version,
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


def to_json(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, collections.abc.Mapping):
        return {
            (k if isinstance(k, str) else str(k)): to_json(v) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, pathlib.PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    if callable(getattr(value, "to_dict", None)):
        return to_json(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            k: to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


# ---------------------------------------------------------------------------
# CLI


class _UsageError(Exception):
    pass


_VALUE_FLAGS = (
    "--model",
    "--seed",
    "--retry-feedback",
    "--max-attempts",
    "--mode",
    "--repo-root",
    "--format",
)


def _parse(argv):
    if not argv or argv[0] != "generate":
        raise _UsageError("first word must be 'generate'")
    args = argv[1:]
    component_id = None
    values = {}
    allow_unisolated_exec = False
    i = 0
    while i < len(args):
        token = args[i]
        if token.startswith("--"):
            name, sep, value = token.partition("=")
            if name in _VALUE_FLAGS:
                if not sep:
                    if i + 1 >= len(args):
                        raise _UsageError(f"{name} requires a value")
                    i += 1
                    value = args[i]
                values[name] = value
            elif token == "--allow-unisolated-exec":
                allow_unisolated_exec = True
            else:
                raise _UsageError(f"unknown argument: {token}")
        elif component_id is None:
            component_id = token
        else:
            raise _UsageError(f"unknown argument: {token}")
        i += 1
    return component_id, values, allow_unisolated_exec


def _valid_max_attempts(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _resolve(argv):
    component_id, values, allow_unisolated_exec = _parse(argv)
    if component_id is None:
        raise _UsageError("missing <component-id>")
    if "--model" not in values:
        raise _UsageError("missing --model")

    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {values['--seed']}")

    max_attempts = None
    if "--max-attempts" in values:
        try:
            max_attempts = int(values["--max-attempts"])
        except ValueError:
            max_attempts = None
        if not _valid_max_attempts(max_attempts):
            raise _UsageError(
                f"--max-attempts must be an integer of at least 1: "
                f"{values['--max-attempts']}"
            )

    mode = values.get("--mode")
    if mode is not None and mode not in ("single", "agentic"):
        raise _UsageError(f"invalid --mode: {mode}")

    output_format = values.get("--format", "text")
    if output_format not in ("json", "text"):
        raise _UsageError(f"invalid --format: {output_format}")

    repo_root = Path(values["--repo-root"]) if "--repo-root" in values else Path.cwd()

    if not component_id.startswith("comp-") or not (
        repo_root / "specs" / "components" / component_id[len("comp-"):] / "component.md"
    ).is_file():
        raise _UsageError(f"unknown component: {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    table = {}
    if toml_path.is_file():
        with open(toml_path, "rb") as handle:
            table = tomllib.load(handle).get("generate", {})
    if "max_attempts" in table and not _valid_max_attempts(table["max_attempts"]):
        raise _UsageError(
            f"invalid [generate] max_attempts in {toml_path}: {table['max_attempts']!r}"
        )
    if "mode" in table and table["mode"] not in ("single", "agentic"):
        raise _UsageError(f"invalid [generate] mode in {toml_path}: {table['mode']!r}")

    if max_attempts is None:
        max_attempts = table.get("max_attempts", 3)
    if mode is None:
        mode = table.get("mode", "single")

    retry_feedback = None
    if "--retry-feedback" in values:
        retry_feedback = values["--retry-feedback"].split(",")

    return {
        "component_id": component_id,
        "repo_root": repo_root,
        "model": values["--model"],
        "seed": seed,
        "retry_feedback": retry_feedback,
        "max_attempts": max_attempts,
        "mode": mode,
        "allow_unisolated_exec": allow_unisolated_exec,
        "format": output_format,
    }


def _print_text(result):
    lines = [result["component_id"]]
    if result["provenance_hit"]:
        lines.append("provenance hit")
    elif result["reverified"]:
        lines.append("reverified")
    elif result["blocked"]:
        lines.append(str(result["block_reason"]))
    else:
        lines.append("passed")
    for attempt in result["attempts"] or []:
        lines.append(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    lines.append(
        f"license_scan blocked: {json.dumps(to_json(_get(license_scan, 'blocked')))}"
    )
    lines.append(
        f"secret_scan flagged: {json.dumps(to_json(_get(secret_scan, 'flagged')))}"
    )
    error = result["model_call_error"]
    if error:
        lines.append(
            f"model_call_error: {_get(error, 'category')}: {_get(error, 'message')}"
        )
    if result["block_reason"] == "surface_check_failed":
        for finding in _get(result["surface_report"], "findings") or []:
            lines.append(f"surface: {_get(finding, 'message')}")
    verification = result["verification"]
    if result["block_reason"] == "test_authoring_failed":
        for criterion in _get(verification, "criteria") or []:
            if _get(criterion, "result") == "fail":
                message = _get(_get(criterion, "failure_detail"), "message")
                lines.append(f"{_get(criterion, 'id')}: {message}")
    mutation_error = _get(verification, "mutation_error")
    if mutation_error:
        lines.append(f"mutation_error: {_get(mutation_error, 'message', mutation_error)}")
    if _get(license_scan, "evaluated") is False:
        lines.append(f"license_scan not evaluated: {_get(license_scan, 'reason')}")
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        options = _resolve(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    result = run_component_gates(
        options["component_id"],
        options["repo_root"],
        options["model"],
        options["seed"],
        None,
        options["retry_feedback"],
        max_attempts=options["max_attempts"],
        mode=options["mode"],
        allow_unisolated_exec=options["allow_unisolated_exec"],
    )

    if options["format"] == "json":
        print(json.dumps(to_json(result)))
    else:
        _print_text(result)

    if _get(result, "block_reason") in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
