"""Component Gate Runner: runs one component through its gauntlet.

Provenance check, generation on a miss, verification, compliance scanning
and provenance write, giving one ``ComponentPipelineResult`` dict.
``main`` implements ``hotdocs generate``.
"""

import dataclasses
import enum
import importlib.util
import itertools
import json
import math
import re
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path, PurePath

USAGE = (
    "usage: hotdocs generate <component-id> --model=<model-id> [--seed=<n>] "
    "[--retry-feedback=<R-id>,...] [--reauthor=<AC-id>,...] [--max-attempts=<n>] "
    "[--mode=single|agentic] [--allow-unisolated-exec] [--repo-root=<dir>] "
    "[--format=json|text]"
)

_VALUE_FLAGS = (
    "--model",
    "--seed",
    "--retry-feedback",
    "--reauthor",
    "--max-attempts",
    "--mode",
    "--repo-root",
    "--format",
)

_MODES = ("single", "agentic")
_FORMATS = ("json", "text")

_load_counter = itertools.count()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _get(obj, name):
    """Dual dict-or-attribute access; an absent field reads as None."""
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _tool_root():
    here = Path(__file__).absolute()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load(slug, repo_root):
    module = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module}.py"
    name = f"_component_gate_runner_dep_{module}_{next(_load_counter)}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Deps:
    """Loads each dependency afresh per run, only when first needed."""

    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._mods = {}

    def __call__(self, slug):
        if slug not in self._mods:
            self._mods[slug] = _load(slug, self._repo_root)
        return self._mods[slug]


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


def _verification_block_reason(report):
    failed = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    if failed and all(_get(c, "failure_origin") == "test" for c in failed):
        return "test_authoring_failed"
    return "verification_failed"


def _scans(deps, component_id, repo_root):
    license_scan = deps("license-scanner").scan(component_id, repo_root)
    secret_scan = deps("secret-scanner").scan(repo_root)
    return license_scan, secret_scan


def _verify_committed(deps, component_id, repo_root, model, seed, llm_backend):
    test_author, judge = deps("generation-loop").make_closures(model, seed, repo_root, llm_backend)
    return deps("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author
    )


def _delete_reauthored(component_id, repo_root, reauthor):
    base = Path(repo_root) / "verification" / _slug(component_id) / "generated-test"
    for criterion_id in reauthor or []:
        path = base / f"test_{criterion_id.lower().replace('-', '_')}.py"
        if path.exists():
            path.unlink()


def _count_attempt_files(component_id, repo_root):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return len([p for p in directory.iterdir() if p.is_file()])


# ---------------------------------------------------------------------------
# library
# ---------------------------------------------------------------------------


def _run_sealed(deps, component_id, repo_root, model, seed, llm_backend, sealed_key):
    report = _verify_committed(deps, component_id, repo_root, model, seed, llm_backend)
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


def _try_reverify(deps, component_id, repo_root, model, seed, llm_backend,
                  spec_bundle_hash, gate_versions):
    report = _verify_committed(deps, component_id, repo_root, model, seed, llm_backend)
    license_scan, secret_scan = _scans(deps, component_id, repo_root)
    if _get(report, "overall") != "pass" or _get(license_scan, "blocked") is True:
        return None
    manifest_path = Path(repo_root) / "gen" / _slug(component_id) / ".provenance.json"
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


def run_component_gates(
    component_id, repo_root, model, seed=0, llm_backend=None, retry_feedback=None, *,
    max_attempts=3, mode="single", allow_unisolated_exec=False, reauthor=None,
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

    _delete_reauthored(component_id, repo_root, reauthor)

    if _get(check, "reason") == "environment differs":
        reverified = _try_reverify(
            deps, component_id, repo_root, model, seed, llm_backend,
            spec_bundle_hash, gate_versions,
        )
        if reverified is not None:
            return reverified

    bundle = deps("spec-bundle-assembler").assemble(component_id, repo_root=repo_root, mode="cold")

    def on_attempt(attempt, generation_result, verification_report):
        try:
            deps("provenance-tracker").write_attempt_record(
                component_id, generation_result, verification_report,
                spec_bundle_hash, repo_root,
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
        outcome = _get(attempts[-1], "outcome")
        if outcome == "verification_failed":
            block_reason = _verification_block_reason(verification_report)
        else:
            block_reason = {
                "generation_failed": "model_call_error",
                "surface_failed": "surface_check_failed",
                "refused": "refused",
            }[outcome]
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


# ---------------------------------------------------------------------------
# JSON conversion (specs/architecture/json-values.md)
# ---------------------------------------------------------------------------


def to_json(value):
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
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_json(to_dict())
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


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _is_sealed(component_md):
    lines = component_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return False
        if re.fullmatch(r"sealed:\s*true", stripped):
            return True
    return False


def _is_generated_test_criterion(spec_dir, criterion_id):
    if not re.fullmatch(r"AC-[A-Za-z0-9-]+", criterion_id):
        return False
    path = spec_dir / "acceptance" / f"{criterion_id}.md"
    if not path.is_file():
        return False
    return any(
        line.strip() == "Kind: generated-test"
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _text_lines(result):
    lines = [str(_get(result, "component_id"))]
    if _get(result, "provenance_hit"):
        lines.append("provenance hit")
    elif _get(result, "reverified"):
        lines.append("reverified")
    else:
        lines.append(str(_get(result, "block_reason") or "passed"))
    for attempt in _get(result, "attempts") or []:
        lines.append(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = _get(result, "license_scan")
    secret_scan = _get(result, "secret_scan")
    lines.append(f"license_scan blocked: {json.dumps(to_json(_get(license_scan, 'blocked')))}")
    lines.append(f"secret_scan flagged: {json.dumps(to_json(_get(secret_scan, 'flagged')))}")
    model_call_error = _get(result, "model_call_error")
    if model_call_error is not None:
        lines.append(
            f"model_call_error: {_get(model_call_error, 'category')}: "
            f"{_get(model_call_error, 'message')}"
        )
    block_reason = _get(result, "block_reason")
    verification = _get(result, "verification")
    if block_reason == "surface_check_failed":
        for finding in _get(_get(result, "surface_report"), "findings") or []:
            lines.append(f"surface: {_get(finding, 'message')}")
    if block_reason == "test_authoring_failed":
        for criterion in _get(verification, "criteria") or []:
            if _get(criterion, "result") == "fail":
                message = _get(_get(criterion, "failure_detail"), "message")
                lines.append(f"{_get(criterion, 'id')}: {message}")
    mutation_error = _get(verification, "mutation_error")
    if mutation_error is not None:
        lines.append(f"mutation_error: {mutation_error}")
    if _get(license_scan, "evaluated") is False:
        lines.append(f"license_scan not evaluated: {_get(license_scan, 'reason')}")
    return lines


def main(argv=None):
    tokens = list(sys.argv[1:] if argv is None else argv)
    if not tokens or tokens[0] != "generate":
        return _usage_error("expected first word 'generate'")

    values = {}
    positional = []
    allow_unisolated_exec = False
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token == "--allow-unisolated-exec":
            allow_unisolated_exec = True
        elif token.startswith("--"):
            name, eq, value = token.partition("=")
            if name not in _VALUE_FLAGS:
                return _usage_error(f"unknown argument {token}")
            if not eq:
                if i + 1 >= len(tokens):
                    return _usage_error(f"{name} needs a value")
                i += 1
                value = tokens[i]
            values[name] = value
        else:
            if positional:
                return _usage_error(f"unknown argument {token}")
            positional.append(token)
        i += 1

    if not positional:
        return _usage_error("missing <component-id>")
    component_id = positional[0]
    if "--model" not in values:
        return _usage_error("missing --model")
    model = values["--model"]

    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        return _usage_error(f"--seed must be an integer: {values['--seed']}")

    flag_max_attempts = None
    if "--max-attempts" in values:
        try:
            flag_max_attempts = int(values["--max-attempts"])
        except ValueError:
            return _usage_error("--max-attempts must be an integer of at least 1")
        if flag_max_attempts < 1:
            return _usage_error("--max-attempts must be an integer of at least 1")

    flag_mode = values.get("--mode")
    if flag_mode is not None and flag_mode not in _MODES:
        return _usage_error(f"--mode must be single or agentic: {flag_mode}")

    output_format = values.get("--format", "text")
    if output_format not in _FORMATS:
        return _usage_error(f"--format must be json or text: {output_format}")

    repo_root = Path(values.get("--repo-root", "."))
    spec_dir = repo_root / "specs" / "components" / _slug(component_id)
    component_md = spec_dir / "component.md"
    if not component_id.startswith("comp-") or not component_md.is_file():
        return _usage_error(f"unknown component {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    table = {}
    if toml_path.is_file():
        with open(toml_path, "rb") as fh:
            table = tomllib.load(fh).get("generate", {})
    file_max_attempts = table.get("max_attempts")
    if "max_attempts" in table and not (
        isinstance(file_max_attempts, int)
        and not isinstance(file_max_attempts, bool)
        and file_max_attempts >= 1
    ):
        return _usage_error(
            f"{toml_path}: [generate] max_attempts must be an integer of at least 1"
        )
    file_mode = table.get("mode")
    if "mode" in table and file_mode not in _MODES:
        return _usage_error(f"{toml_path}: [generate] mode must be single or agentic")

    if flag_max_attempts is not None:
        max_attempts = flag_max_attempts
    elif file_max_attempts is not None:
        max_attempts = file_max_attempts
    else:
        max_attempts = 3
    mode = flag_mode or file_mode or "single"

    retry_feedback = None
    if "--retry-feedback" in values:
        retry_feedback = values["--retry-feedback"].split(",")

    reauthor = None
    if "--reauthor" in values:
        reauthor = values["--reauthor"].split(",")
        if any(not entry for entry in reauthor):
            return _usage_error("--reauthor needs criterion ids")
        if _is_sealed(component_md):
            return _usage_error(f"--reauthor does not apply to sealed {component_id}")
        for criterion_id in reauthor:
            if not _is_generated_test_criterion(spec_dir, criterion_id):
                return _usage_error(
                    f"{criterion_id} is not a generated-test criterion of {component_id}"
                )

    result = run_component_gates(
        component_id, repo_root, model, seed, None, retry_feedback,
        max_attempts=max_attempts, mode=mode,
        allow_unisolated_exec=allow_unisolated_exec, reauthor=reauthor,
    )

    if output_format == "json":
        print(json.dumps(to_json(result)))
    else:
        print("\n".join(_text_lines(result)))

    if _get(result, "block_reason") in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
