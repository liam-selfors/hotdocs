"""Component Gate Runner: runs one component through its gauntlet.

`run_component_gates` sequences provenance check, generation (via
generation-loop), verification, compliance scans and provenance writes;
`main` implements the `hotdocs generate` command line.
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

_REVERIFY_REASONS = ("environment differs", "dependency code differs")


# ---------------------------------------------------------------------------
# helpers


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _tool_root():
    here = Path(__file__).resolve().parent
    return next(d.parent for d in (here, *here.parents) if d.name == "gen")


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


class _Deps:
    """Loads each dependency afresh per run, only on its first use."""

    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._mods = {}

    def __call__(self, slug):
        if slug not in self._mods:
            self._mods[slug] = _load(slug, self._repo_root)
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


def _verification_block_reason(report):
    fails = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    if fails and all(_get(c, "failure_origin") == "test" for c in fails):
        return "test_authoring_failed"
    return "verification_failed"


def _count_attempt_files(repo_root, component_id):
    d = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not d.is_dir():
        return 0
    return sum(1 for p in d.iterdir() if p.is_file())


# ---------------------------------------------------------------------------
# library


def run_component_gates(
    component_id, repo_root, model, seed=0, llm_backend=None,
    retry_feedback=None, *, max_attempts=3, mode="single",
    allow_unisolated_exec=False, reauthor=None,
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

    slug = _slug(component_id)
    for criterion_id in reauthor or []:
        test_file = (
            Path(repo_root) / "verification" / slug / "generated-test"
            / f"test_{criterion_id.lower().replace('-', '_')}.py"
        )
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
                "spec_bundle_parts": spec_bundle_parts,
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
            "spec_bundle_parts": spec_bundle_parts,
        }
        deps("provenance-writer").write_provenance(component_id, inputs, repo_root)

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
        else:
            block_reason = _verification_block_reason(verification_report)

    return _result(
        component_id,
        blocked=blocked,
        block_reason=block_reason,
        model_call_error=model_call_error,
        surface_report=_get(loop, "surface_report"),
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


def _to_json(value):
    try:
        if value is None or isinstance(value, (bool, int, str)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else repr(value)
        if isinstance(value, Mapping):
            return {
                (k if isinstance(k, str) else str(k)): _to_json(v)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [_to_json(v) for v in value]
        if isinstance(value, (set, frozenset)):
            items = [_to_json(v) for v in value]
            return sorted(items, key=lambda i: json.dumps(i, sort_keys=True))
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, PurePath):
            return str(value)
        if isinstance(value, enum.Enum):
            return _to_json(value.value)
        if callable(getattr(value, "to_dict", None)):
            return _to_json(value.to_dict())
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return {f.name: _to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
        if hasattr(value, "__dict__"):
            return {
                k: _to_json(v)
                for k, v in vars(value).items()
                if not k.startswith("_") and not callable(v)
            }
        return repr(value)
    except Exception:
        return repr(value)


# ---------------------------------------------------------------------------
# CLI


class _UsageError(Exception):
    pass


def _is_sealed(component_md):
    lines = component_md.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            name, _, val = line.partition(":")
            if name.strip() == "sealed" and val.strip() == "true":
                return True
    return False


def _is_generated_test_criterion(repo_root, slug, criterion_id):
    if not re.fullmatch(r"AC-[A-Za-z0-9-]+", criterion_id):
        return False
    path = repo_root / "specs" / "components" / slug / "acceptance" / f"{criterion_id}.md"
    if not path.is_file():
        return False
    return any(
        line.strip() == "Kind: generated-test"
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _parse(argv):
    if not argv or argv[0] != "generate":
        raise _UsageError("expected first word 'generate'")
    tokens = argv[1:]
    positionals = []
    opts = {}
    allow = False
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "--allow-unisolated-exec":
            allow = True
            i += 1
            continue
        if token.startswith("-"):
            name, eq, val = token.partition("=")
            if name not in _VALUE_FLAGS:
                raise _UsageError(f"unknown argument {token}")
            if eq:
                i += 1
            else:
                if i + 1 >= len(tokens):
                    raise _UsageError(f"{name} needs a value")
                val = tokens[i + 1]
                i += 2
            opts[name] = val
            continue
        positionals.append(token)
        i += 1
    if not positionals:
        raise _UsageError("missing <component-id>")
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument {positionals[1]}")
    return positionals[0], opts, allow


def _validate(argv):
    component_id, opts, allow = _parse(argv)

    if "--model" not in opts:
        raise _UsageError("missing --model")
    model = opts["--model"]

    fmt = opts.get("--format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format {fmt}")

    mode = opts.get("--mode")
    if mode is not None and mode not in ("single", "agentic"):
        raise _UsageError(f"invalid --mode {mode}")

    try:
        seed = int(opts.get("--seed", "0"))
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {opts['--seed']}")

    max_attempts = None
    if "--max-attempts" in opts:
        raw = opts["--max-attempts"]
        try:
            max_attempts = int(raw)
        except ValueError:
            raise _UsageError(f"--max-attempts must be an integer of at least 1: {raw}")
        if max_attempts < 1:
            raise _UsageError(f"--max-attempts must be an integer of at least 1: {raw}")

    repo_root = Path(opts.get("--repo-root", "."))
    slug = _slug(component_id)
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_md.is_file():
        raise _UsageError(f"unknown component {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    file_values = {}
    if toml_path.is_file():
        with open(toml_path, "rb") as fh:
            file_values = tomllib.load(fh).get("generate", {})
    if "max_attempts" in file_values:
        v = file_values["max_attempts"]
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise _UsageError(
                f"{toml_path}: [generate] max_attempts must be an integer of at least 1"
            )
    if "mode" in file_values and file_values["mode"] not in ("single", "agentic"):
        raise _UsageError(f"{toml_path}: [generate] mode must be single or agentic")

    if max_attempts is None:
        max_attempts = file_values.get("max_attempts", 3)
    if mode is None:
        mode = file_values.get("mode", "single")

    retry_feedback = None
    if "--retry-feedback" in opts:
        retry_feedback = opts["--retry-feedback"].split(",")

    reauthor = None
    if "--reauthor" in opts:
        reauthor = opts["--reauthor"].split(",")
        if any(entry == "" for entry in reauthor):
            raise _UsageError("--reauthor needs criterion ids")
        if _is_sealed(component_md):
            raise _UsageError(f"--reauthor does not apply to sealed {component_id}")
        for criterion_id in reauthor:
            if not _is_generated_test_criterion(repo_root, slug, criterion_id):
                raise _UsageError(
                    f"{criterion_id} is not a generated-test criterion of {component_id}"
                )

    return {
        "component_id": component_id,
        "repo_root": repo_root,
        "model": model,
        "seed": seed,
        "retry_feedback": retry_feedback,
        "max_attempts": max_attempts,
        "mode": mode,
        "allow_unisolated_exec": allow,
        "reauthor": reauthor,
        "format": fmt,
    }


def _print_text(result):
    lines = [str(_get(result, "component_id"))]
    if _get(result, "provenance_hit"):
        lines.append("provenance hit")
    elif _get(result, "reverified"):
        lines.append("reverified")
    elif _get(result, "blocked"):
        lines.append(str(_get(result, "block_reason")))
    else:
        lines.append("passed")
    for attempt in _get(result, "attempts") or []:
        lines.append(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = _get(result, "license_scan")
    secret_scan = _get(result, "secret_scan")
    lines.append(f"license_scan blocked: {json.dumps(_to_json(_get(license_scan, 'blocked')))}")
    lines.append(f"secret_scan flagged: {json.dumps(_to_json(_get(secret_scan, 'flagged')))}")

    mce = _get(result, "model_call_error")
    if mce is not None:
        lines.append(f"model_call_error: {_get(mce, 'category')}: {_get(mce, 'message')}")

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
        message = mutation_error if isinstance(mutation_error, str) else _get(mutation_error, "message")
        lines.append(f"mutation_error: {message}")

    if _get(license_scan, "evaluated") is False:
        lines.append(f"license_scan not evaluated: {_get(license_scan, 'reason')}")

    print("\n".join(lines))


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = _validate(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    result = run_component_gates(
        args["component_id"], args["repo_root"], args["model"], args["seed"],
        retry_feedback=args["retry_feedback"],
        max_attempts=args["max_attempts"], mode=args["mode"],
        allow_unisolated_exec=args["allow_unisolated_exec"],
        reauthor=args["reauthor"],
    )

    if args["format"] == "json":
        print(json.dumps(_to_json(result)))
    else:
        _print_text(result)

    if _get(result, "block_reason") in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
