"""Component Gate Runner: runs one component through its gauntlet.

`run_component_gates` sequences provenance check, generation on a miss,
verification, compliance scanning and provenance write, giving one
`ComponentPipelineResult`. `main` implements `hotdocs generate`.
"""

from __future__ import annotations

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

_COUNTER = itertools.count()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, name):
    """Dual dict-or-attribute access; an absent field reads as None."""
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_module(slug, repo_root):
    module = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.exists():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module}.py"
    name = f"_component_gate_runner_dep_{module}_{next(_COUNTER)}"
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

    def get(self, slug):
        if slug not in self._mods:
            self._mods[slug] = _load_module(slug, self._repo_root)
        return self._mods[slug]


def _result(component_id, *, provenance_hit=False, reverified=False,
            blocked=False, block_reason=None, model_call_error=None,
            surface_report=None, verification=None, attempts=None,
            license_scan=None, secret_scan=None):
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


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _is_test_authoring_failure(report):
    failed = [c for c in (_get(report, "criteria") or [])
              if _get(c, "result") == "fail"]
    return bool(failed) and all(_get(c, "failure_origin") == "test" for c in failed)


def _count_attempt_files(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file())


def _delete_reauthored(component_id, repo_root, reauthor):
    if reauthor is None:
        return
    base = Path(repo_root) / "verification" / _slug(component_id) / "generated-test"
    for criterion_id in reauthor:
        path = base / f"test_{criterion_id.lower().replace('-', '_')}.py"
        if path.exists():
            path.unlink()


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def run_component_gates(
    component_id, repo_root, model, seed=0, llm_backend=None,
    retry_feedback=None, *, max_attempts=3, mode="single",
    allow_unisolated_exec=False, reauthor=None,
):
    deps = _Deps(repo_root)
    checker = deps.get("provenance-checker")
    sealed_key = checker.current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(component_id, repo_root, model, seed, llm_backend,
                           sealed_key, deps)

    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = checker.check_provenance(component_id, spec_bundle_hash,
                                     gate_versions, repo_root)

    if (_get(check, "hit")
            and _get(_get(check, "verification_report"), "overall") == "pass"
            and _get(_get(check, "license_scan"), "blocked") is not True):
        return _result(
            component_id, provenance_hit=True,
            verification=_get(check, "verification_report"),
            license_scan=_get(check, "license_scan"),
            secret_scan=_get(check, "secret_scan"),
        )

    _delete_reauthored(component_id, repo_root, reauthor)

    if _get(check, "reason") == "environment differs":
        reverified = _reverify(component_id, repo_root, model, seed,
                               llm_backend, spec_bundle_hash, gate_versions,
                               deps)
        if reverified is not None:
            return reverified

    bundle = deps.get("spec-bundle-assembler").assemble(
        component_id, repo_root=repo_root, mode="cold")

    def on_attempt(attempt, generation_result, verification_report):
        try:
            deps.get("provenance-tracker").write_attempt_record(
                component_id, generation_result, verification_report,
                spec_bundle_hash, repo_root)
        except Exception:
            pass

    loop = deps.get("generation-loop").run_attempts(
        component_id, bundle, repo_root, model, mode=mode,
        max_attempts=max_attempts, retry_feedback=retry_feedback, seed=seed,
        llm_backend=llm_backend, allow_unisolated_exec=allow_unisolated_exec,
        on_attempt=on_attempt)

    license_scan = deps.get("license-scanner").scan(component_id, repo_root)
    secret_scan = deps.get("secret-scanner").scan(repo_root)

    generation_result = _get(loop, "generation_result")
    verification_report = _get(loop, "verification_report")
    attempts = _get(loop, "attempts")

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
        deps.get("provenance-writer").write_provenance(component_id, inputs,
                                                       repo_root)

    blocked = False
    block_reason = None
    model_call_error = None
    if not _get(loop, "passed"):
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
        model_call_error=model_call_error,
        surface_report=_get(loop, "surface_report"),
        verification=verification_report, attempts=attempts,
        license_scan=license_scan, secret_scan=secret_scan,
    )


def _reverify(component_id, repo_root, model, seed, llm_backend,
              spec_bundle_hash, gate_versions, deps):
    test_author, judge = deps.get("generation-loop").make_closures(
        model, seed, repo_root, llm_backend)
    report = deps.get("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author)
    license_scan = deps.get("license-scanner").scan(component_id, repo_root)
    secret_scan = deps.get("secret-scanner").scan(repo_root)
    if not (_get(report, "overall") == "pass"
            and _get(license_scan, "blocked") is not True):
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
    deps.get("provenance-writer").write_provenance(component_id, inputs,
                                                   repo_root)
    return _result(component_id, reverified=True, verification=report,
                   license_scan=license_scan, secret_scan=secret_scan)


def _run_sealed(component_id, repo_root, model, seed, llm_backend,
                sealed_key, deps):
    owners = _get(sealed_key, "owners")
    source_path = _get(sealed_key, "source_path")
    source_hash = _get(sealed_key, "source_hash")
    verifier_version = _get(sealed_key, "verifier_version")

    test_author, judge = deps.get("generation-loop").make_closures(
        model, seed, repo_root, llm_backend)
    report = deps.get("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author)
    license_scan = deps.get("license-scanner").scan(component_id, repo_root)
    secret_scan = deps.get("secret-scanner").scan(repo_root)

    inputs = {
        "component_id": component_id,
        "owners": owners,
        "source_path": source_path,
        "source_hash": source_hash,
        "verifier_version": verifier_version,
        "verification_report": report,
    }
    deps.get("provenance-writer").write_sealed_provenance(component_id, inputs,
                                                          repo_root)

    blocked = _get(report, "overall") == "fail"
    return _result(
        component_id, blocked=blocked,
        block_reason="verification_failed" if blocked else None,
        verification=report, license_scan=license_scan,
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
        return {(k if isinstance(k, str) else str(k)): to_json(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_json(to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json(getattr(value, f.name))
                for f in dataclasses.fields(value)}
    if hasattr(value, "__dict__"):
        return {k: to_json(v) for k, v in vars(value).items()
                if not k.startswith("_") and not callable(v)}
    return repr(value)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_USAGE = (
    "usage: hotdocs generate <component-id> --model=<model-id> [--seed=<n>] "
    "[--retry-feedback=<R-id>,...] [--reauthor=<AC-id>,...] "
    "[--max-attempts=<n>] [--mode=single|agentic] [--allow-unisolated-exec] "
    "[--repo-root=<dir>] [--format=json|text]"
)

_VALUE_FLAGS = ("--model", "--seed", "--retry-feedback", "--reauthor",
                "--max-attempts", "--mode", "--repo-root", "--format")
_MODES = ("single", "agentic")
_FORMATS = ("json", "text")


class _UsageError(Exception):
    pass


def _parse(tokens):
    values = {}
    positionals = []
    allow = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--allow-unisolated-exec":
            allow = True
        elif tok.startswith("-"):
            name, eq, val = tok.partition("=")
            if name not in _VALUE_FLAGS:
                raise _UsageError(f"unknown argument: {tok}")
            if not eq:
                if i + 1 >= len(tokens):
                    raise _UsageError(f"{name} needs a value")
                i += 1
                val = tokens[i]
            values[name] = val
        else:
            if positionals:
                raise _UsageError(f"unknown argument: {tok}")
            positionals.append(tok)
        i += 1
    return values, positionals, allow


def _valid_max_attempts(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _frontmatter_sealed(component_md):
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


def _is_generated_test_criterion(spec_dir, criterion_id):
    if not re.fullmatch(r"AC-[A-Za-z0-9-]+", criterion_id):
        return False
    path = spec_dir / "acceptance" / f"{criterion_id}.md"
    if not path.is_file():
        return False
    return any(line.strip() == "Kind: generated-test"
               for line in path.read_text(encoding="utf-8").splitlines())


def _parse_args(argv):
    if not argv or argv[0] != "generate":
        raise _UsageError('expected "generate" as the first word')
    values, positionals, allow = _parse(argv[1:])
    if not positionals:
        raise _UsageError("missing <component-id>")
    component_id = positionals[0]
    model = values.get("--model")
    if model is None:
        raise _UsageError("missing --model")

    seed = 0
    if "--seed" in values:
        try:
            seed = int(values["--seed"])
        except ValueError:
            raise _UsageError(f"--seed must be an integer: {values['--seed']}")

    max_attempts = None
    if "--max-attempts" in values:
        try:
            max_attempts = int(values["--max-attempts"])
        except ValueError:
            max_attempts = 0
        if max_attempts < 1:
            raise _UsageError(
                f"--max-attempts must be an integer of at least 1: "
                f"{values['--max-attempts']}")

    mode = values.get("--mode")
    if mode is not None and mode not in _MODES:
        raise _UsageError(f"--mode must be single or agentic: {mode}")

    fmt = values.get("--format", "text")
    if fmt not in _FORMATS:
        raise _UsageError(f"--format must be json or text: {fmt}")

    repo_root = Path(values.get("--repo-root", "."))
    spec_dir = repo_root / "specs" / "components" / _slug(component_id)
    if (not component_id.startswith("comp-")
            or not (spec_dir / "component.md").is_file()):
        raise _UsageError(f"unknown component: {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    if toml_path.is_file():
        with open(toml_path, "rb") as fh:
            table = tomllib.load(fh).get("generate", {})
        if "max_attempts" in table:
            if not _valid_max_attempts(table["max_attempts"]):
                raise _UsageError(
                    f"invalid [generate] max_attempts in {toml_path}")
            if max_attempts is None:
                max_attempts = table["max_attempts"]
        if "mode" in table:
            if table["mode"] not in _MODES:
                raise _UsageError(f"invalid [generate] mode in {toml_path}")
            if mode is None:
                mode = table["mode"]

    retry_feedback = None
    if "--retry-feedback" in values:
        retry_feedback = values["--retry-feedback"].split(",")

    reauthor = None
    if "--reauthor" in values:
        reauthor = values["--reauthor"].split(",")
        if any(entry == "" for entry in reauthor):
            raise _UsageError("--reauthor needs criterion ids")
        if _frontmatter_sealed(spec_dir / "component.md"):
            raise _UsageError(
                f"--reauthor does not apply to sealed {component_id}")
        for criterion_id in reauthor:
            if not _is_generated_test_criterion(spec_dir, criterion_id):
                raise _UsageError(
                    f"{criterion_id} is not a generated-test criterion of "
                    f"{component_id}")

    return {
        "component_id": component_id,
        "repo_root": repo_root,
        "model": model,
        "seed": seed,
        "retry_feedback": retry_feedback,
        "max_attempts": 3 if max_attempts is None else max_attempts,
        "mode": "single" if mode is None else mode,
        "allow_unisolated_exec": allow,
        "reauthor": reauthor,
        "format": fmt,
    }


def _flag_text(value):
    return json.dumps(to_json(value))


def _print_text(result):
    if result["provenance_hit"]:
        status = "provenance hit"
    elif result["reverified"]:
        status = "reverified"
    elif result["blocked"]:
        status = result["block_reason"]
    else:
        status = "passed"
    print(f"{result['component_id']}: {status}")
    for attempt in result["attempts"] or []:
        print(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    print(f"license_scan blocked: {_flag_text(_get(license_scan, 'blocked'))}")
    print(f"secret_scan flagged: {_flag_text(_get(secret_scan, 'flagged'))}")

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
                message = _get(_get(criterion, "failure_detail"), "message")
                print(f"{_get(criterion, 'id')}: {message}")
    mutation_error = _get(verification, "mutation_error")
    if mutation_error is not None:
        message = (mutation_error if isinstance(mutation_error, str)
                   else _get(mutation_error, "message"))
        print(f"mutation_error: {message}")
    if _get(license_scan, "evaluated") is False:
        print(f"license_scan not evaluated: {_get(license_scan, 'reason')}")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = _parse_args(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2

    result = run_component_gates(
        args["component_id"], args["repo_root"], args["model"], args["seed"],
        None, args["retry_feedback"],
        max_attempts=args["max_attempts"], mode=args["mode"],
        allow_unisolated_exec=args["allow_unisolated_exec"],
        reauthor=args["reauthor"],
    )

    if args["format"] == "json":
        print(json.dumps(to_json(result)))
    else:
        _print_text(result)

    if result["block_reason"] in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
