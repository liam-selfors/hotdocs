"""Component gate runner: runs one component through its gauntlet.

Provenance check, generation on a miss (via generation-loop), verification,
compliance scanning and provenance write, giving one ComponentPipelineResult.
Also the `hotdocs generate` CLI (`main`).
"""

import dataclasses
import enum
import importlib.util
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

_REVERIFY_REASONS = (
    "environment differs",
    "dependency code differs",
    "hash formula differs",
    "gates differ",
)

_BLOCK_REASONS = {
    "generation_failed": "model_call_error",
    "surface_failed": "surface_check_failed",
    "refused": "refused",
}

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


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load(slug, repo_root):
    module_name = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _Deps:
    """Loads each dependency afresh per run, lazily, once per run."""

    def __init__(self, repo_root):
        self.repo_root = repo_root
        self.modules = {}

    def __call__(self, slug):
        if slug not in self.modules:
            self.modules[slug] = _load(slug, self.repo_root)
        return self.modules[slug]


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _result(component_id, *, provenance_hit=False, reverified=False, blocked=False,
            block_reason=None, model_call_error=None, surface_report=None,
            verification=None, attempts, license_scan, secret_scan):
    return {
        "component_id": component_id,
        "provenance_hit": provenance_hit,
        "reverified": reverified,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": model_call_error,
        "surface_report": surface_report,
        "verification": verification,
        "attempts": attempts,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _test_authoring_failed(report):
    fails = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    return bool(fails) and all(_get(c, "failure_origin") == "test" for c in fails)


def _count_attempt_files(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file())


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------

def run_component_gates(
    component_id, repo_root, model, seed=0, llm_backend=None, retry_feedback=None, *,
    max_attempts=3, mode="single", allow_unisolated_exec=False, reauthor=None,
):
    deps = _Deps(repo_root)

    sealed_key = deps("provenance-checker").current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(deps, component_id, repo_root, model, seed, llm_backend, sealed_key)

    checker = deps("provenance-checker")
    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    spec_bundle_parts = _get(key, "spec_bundle_parts")
    check = checker.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts
    )

    hit_report = _get(check, "verification_report")
    hit_license = _get(check, "license_scan")
    if (_get(check, "hit") and _get(hit_report, "overall") == "pass"
            and _get(hit_license, "blocked") is not True):
        return _result(
            component_id,
            provenance_hit=True,
            verification=hit_report,
            attempts=[],
            license_scan=hit_license,
            secret_scan=_get(check, "secret_scan"),
        )

    slug = _slug(component_id)
    for criterion_id in reauthor or []:
        test_file = (Path(repo_root) / "verification" / slug / "generated-test"
                     / f"test_{criterion_id.lower().replace('-', '_')}.py")
        if test_file.exists():
            test_file.unlink()

    if _get(check, "reason") in _REVERIFY_REASONS:
        test_author, judge = deps("generation-loop").make_closures(
            model, seed, repo_root, llm_backend
        )
        report = deps("verifier-orchestrator").verify(
            component_id, repo_root, judge=judge, test_author=test_author
        )
        license_scan = deps("license-scanner").scan(component_id, repo_root)
        secret_scan = deps("secret-scanner").scan(repo_root)
        if _get(report, "overall") == "pass" and _get(license_scan, "blocked") is not True:
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
                "spec_bundle_parts": spec_bundle_parts,
            }
            deps("provenance-writer").write_provenance(component_id, inputs, repo_root)
            return _result(
                component_id,
                reverified=True,
                verification=report,
                attempts=[],
                license_scan=license_scan,
                secret_scan=secret_scan,
            )

    bundle = deps("spec-bundle-assembler").assemble(
        component_id, repo_root=repo_root, mode="cold"
    )

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

    license_scan = deps("license-scanner").scan(component_id, repo_root)
    secret_scan = deps("secret-scanner").scan(repo_root)

    attempts = _get(loop, "attempts")
    generation_result = _get(loop, "generation_result")
    verification_report = _get(loop, "verification_report")
    surface_report = _get(loop, "surface_report")

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
            "spec_bundle_parts": spec_bundle_parts,
        }
        deps("provenance-writer").write_provenance(component_id, inputs, repo_root)

    blocked = False
    block_reason = None
    model_call_error = None
    if not _get(loop, "passed"):
        blocked = True
        outcome = _get(attempts[-1], "outcome")
        if outcome == "verification_failed":
            block_reason = ("test_authoring_failed"
                            if _test_authoring_failed(verification_report)
                            else "verification_failed")
        else:
            block_reason = _BLOCK_REASONS[outcome]
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

    failed = _get(report, "overall") == "fail"
    return _result(
        component_id,
        blocked=failed,
        block_reason="verification_failed" if failed else None,
        verification=report,
        attempts=[],
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


# --------------------------------------------------------------------------
# JSON conversion (specs/architecture/json-values.md)
# --------------------------------------------------------------------------

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
            k: to_json(v) for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _is_sealed(component_md):
    lines = component_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, val = line.partition(":")
        if key.strip() == "sealed" and val.strip() == "true":
            return True
    return False


def _is_generated_test(path):
    return path.is_file() and any(
        line.strip() == "Kind: generated-test"
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _print_text(result):
    component_id = result["component_id"]
    if result["provenance_hit"]:
        status = "provenance hit"
    elif result["reverified"]:
        status = "reverified"
    elif result["blocked"]:
        status = result["block_reason"]
    else:
        status = "passed"
    print(f"{component_id}: {status}")
    for attempt in result["attempts"]:
        print(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    print(f"license_scan blocked: {json.dumps(to_json(_get(license_scan, 'blocked')))}")
    print(f"secret_scan flagged: {json.dumps(to_json(_get(secret_scan, 'flagged')))}")
    mce = result["model_call_error"]
    if mce is not None:
        print(f"model_call_error: {_get(mce, 'category')}: {_get(mce, 'message')}")
    if result["block_reason"] == "surface_check_failed":
        for finding in _get(result["surface_report"], "findings") or []:
            print(f"surface: {_get(finding, 'message')}")
    verification = result["verification"]
    if result["block_reason"] == "test_authoring_failed":
        for criterion in _get(verification, "criteria") or []:
            if _get(criterion, "result") == "fail":
                detail = _get(criterion, "failure_detail")
                print(f"{_get(criterion, 'id')}: {_get(detail, 'message')}")
    mutation_error = _get(verification, "mutation_error")
    if mutation_error:
        print(f"mutation_error: {mutation_error}")
    if _get(license_scan, "evaluated") is False:
        print(f"license_scan not evaluated: {_get(license_scan, 'reason')}")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv or argv[0] != "generate":
        return _usage_error("expected first word generate")

    flags = {}
    positionals = []
    allow_unisolated_exec = False
    i = 1
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            name, eq, value = token.partition("=")
            if name in _VALUE_FLAGS:
                if not eq:
                    if i + 1 >= len(argv):
                        return _usage_error(f"{name} needs a value")
                    i += 1
                    value = argv[i]
                flags[name] = value
            elif token == "--allow-unisolated-exec":
                allow_unisolated_exec = True
            else:
                return _usage_error(f"unknown argument {token}")
        else:
            if positionals:
                return _usage_error(f"unknown argument {token}")
            positionals.append(token)
        i += 1

    if not positionals:
        return _usage_error("missing <component-id>")
    component_id = positionals[0]
    if "--model" not in flags:
        return _usage_error("missing --model")

    repo_root = Path(flags.get("--repo-root", "."))
    slug = component_id[len("comp-"):]
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_id.startswith("comp-") or not component_md.is_file():
        return _usage_error(f"unknown component {component_id}")

    try:
        seed = int(flags.get("--seed", "0"))
    except ValueError:
        return _usage_error(f"--seed must be an integer: {flags['--seed']}")

    max_attempts = None
    if "--max-attempts" in flags:
        try:
            max_attempts = int(flags["--max-attempts"])
        except ValueError:
            return _usage_error("--max-attempts must be an integer of at least 1")
        if max_attempts < 1:
            return _usage_error("--max-attempts must be an integer of at least 1")

    fmt = flags.get("--format", "text")
    if fmt not in _FORMATS:
        return _usage_error(f"invalid --format {fmt}")

    mode = flags.get("--mode")
    if mode is not None and mode not in _MODES:
        return _usage_error(f"invalid --mode {mode}")

    toml_path = repo_root / "hotdocs.toml"
    table = {}
    if toml_path.is_file():
        with open(toml_path, "rb") as fh:
            table = tomllib.load(fh).get("generate", {})
    if "max_attempts" in table:
        file_value = table["max_attempts"]
        if not (isinstance(file_value, int) and not isinstance(file_value, bool)
                and file_value >= 1):
            return _usage_error(
                f"{toml_path}: [generate] max_attempts must be an integer of at least 1"
            )
        if max_attempts is None:
            max_attempts = file_value
    if "mode" in table:
        file_value = table["mode"]
        if file_value not in _MODES:
            return _usage_error(f"{toml_path}: [generate] mode must be single or agentic")
        if mode is None:
            mode = file_value
    if max_attempts is None:
        max_attempts = 3
    if mode is None:
        mode = "single"

    retry_feedback = None
    if "--retry-feedback" in flags:
        retry_feedback = flags["--retry-feedback"].split(",")

    reauthor = None
    if "--reauthor" in flags:
        ids = flags["--reauthor"].split(",")
        if any(not criterion_id for criterion_id in ids):
            return _usage_error("--reauthor needs criterion ids")
        if _is_sealed(component_md):
            return _usage_error(f"--reauthor does not apply to sealed {component_id}")
        acceptance = repo_root / "specs" / "components" / slug / "acceptance"
        for criterion_id in ids:
            if (not re.fullmatch(r"AC-[A-Za-z0-9-]+", criterion_id)
                    or not _is_generated_test(acceptance / f"{criterion_id}.md")):
                return _usage_error(
                    f"{criterion_id} is not a generated-test criterion of {component_id}"
                )
        reauthor = ids

    result = run_component_gates(
        component_id, repo_root, flags["--model"], seed, None, retry_feedback,
        max_attempts=max_attempts, mode=mode,
        allow_unisolated_exec=allow_unisolated_exec, reauthor=reauthor,
    )

    if fmt == "json":
        print(json.dumps(to_json(result)))
    else:
        _print_text(result)

    if result["block_reason"] in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
