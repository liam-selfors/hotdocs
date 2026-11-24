"""Component Gate Runner: runs one component through its gauntlet.

`run_component_gates` performs the provenance check, generation on a miss,
verification, compliance scanning and provenance write, giving one
`ComponentPipelineResult` dict. `main` implements `hotdocs generate`.
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

_USAGE = (
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
_EXIT_ONE_REASONS = ("model_call_error", "test_authoring_failed")

_load_counter = itertools.count()


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


def _slug(component_id):
    return component_id.removeprefix("comp-")


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


def _verification_block_reason(report):
    fails = [c for c in _get(report, "criteria", []) if _get(c, "result") == "fail"]
    if fails and all(_get(c, "failure_origin") == "test" for c in fails):
        return "test_authoring_failed"
    return "verification_failed"


def _count_attempt_files(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file())


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
    reauthor=None,
):
    loaded = {}

    def dep(slug):
        if slug not in loaded:
            loaded[slug] = _load(slug, repo_root)
        return loaded[slug]

    sealed_key = dep("provenance-checker").current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(component_id, repo_root, model, seed, llm_backend, sealed_key, dep)

    key = dep("provenance-checker").current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = dep("provenance-checker").check_provenance(
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

    if reauthor is not None:
        test_dir = Path(repo_root) / "verification" / _slug(component_id) / "generated-test"
        for criterion_id in reauthor:
            test_file = test_dir / f"test_{criterion_id.lower().replace('-', '_')}.py"
            if test_file.exists():
                test_file.unlink()

    if _get(check, "reason") == "environment differs":
        test_author, judge = dep("generation-loop").make_closures(
            model, seed, repo_root, llm_backend
        )
        report = dep("verifier-orchestrator").verify(
            component_id, repo_root, judge=judge, test_author=test_author
        )
        license_scan = dep("license-scanner").scan(component_id, repo_root)
        secret_scan = dep("secret-scanner").scan(repo_root)
        if (
            _get(report, "overall") == "pass"
            and _get(license_scan, "blocked") is not True
            and _get(secret_scan, "flagged") is not True
        ):
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
            dep("provenance-writer").write_provenance(component_id, inputs, repo_root)
            return _result(
                component_id,
                reverified=True,
                verification=report,
                license_scan=license_scan,
                secret_scan=secret_scan,
            )

    bundle = dep("spec-bundle-assembler").assemble(
        component_id, repo_root=repo_root, mode="cold"
    )

    def on_attempt(attempt, generation_result, verification_report):
        try:
            dep("provenance-tracker").write_attempt_record(
                component_id, generation_result, verification_report, spec_bundle_hash, repo_root
            )
        except Exception:
            pass

    loop = dep("generation-loop").run_attempts(
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

    license_scan = dep("license-scanner").scan(component_id, repo_root)
    secret_scan = dep("secret-scanner").scan(repo_root)

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
        dep("provenance-writer").write_provenance(component_id, inputs, repo_root)

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


def _run_sealed(component_id, repo_root, model, seed, llm_backend, sealed_key, dep):
    owners = _get(sealed_key, "owners")
    source_path = _get(sealed_key, "source_path")
    source_hash = _get(sealed_key, "source_hash")
    verifier_version = _get(sealed_key, "verifier_version")

    test_author, judge = dep("generation-loop").make_closures(model, seed, repo_root, llm_backend)
    report = dep("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author
    )
    license_scan = dep("license-scanner").scan(component_id, repo_root)
    secret_scan = dep("secret-scanner").scan(repo_root)

    inputs = {
        "component_id": component_id,
        "owners": owners,
        "source_path": source_path,
        "source_hash": source_hash,
        "verifier_version": verifier_version,
        "verification_report": report,
    }
    dep("provenance-writer").write_sealed_provenance(component_id, inputs, repo_root)

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
    if dataclasses.is_dataclass(value):
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


def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def _fmt(value):
    return json.dumps(to_json(value))


def _print_text(result):
    block_reason = _get(result, "block_reason")
    print(_get(result, "component_id"))
    if _get(result, "provenance_hit"):
        print("provenance hit")
    elif _get(result, "reverified"):
        print("reverified")
    elif _get(result, "blocked"):
        print(block_reason)
    else:
        print("passed")
    for attempt in _get(result, "attempts"):
        print(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = _get(result, "license_scan")
    secret_scan = _get(result, "secret_scan")
    print(f"license_scan blocked: {_fmt(_get(license_scan, 'blocked'))}")
    print(f"secret_scan flagged: {_fmt(_get(secret_scan, 'flagged'))}")
    model_call_error = _get(result, "model_call_error")
    if model_call_error is not None:
        print(
            f"model_call_error: {_get(model_call_error, 'category')}: "
            f"{_get(model_call_error, 'message')}"
        )
    if block_reason == "surface_check_failed":
        for finding in _get(_get(result, "surface_report"), "findings"):
            print(f"surface: {_get(finding, 'message')}")
    verification = _get(result, "verification")
    if block_reason == "test_authoring_failed":
        for criterion in _get(verification, "criteria"):
            if _get(criterion, "result") == "fail":
                print(
                    f"{_get(criterion, 'id')}: "
                    f"{_get(_get(criterion, 'failure_detail'), 'message')}"
                )
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
        return _usage("expected first word 'generate'")

    opts = {}
    component_id = None
    allow_unisolated_exec = False
    i = 1
    while i < len(argv):
        token = argv[i]
        if token == "--allow-unisolated-exec":
            allow_unisolated_exec = True
        elif token.startswith("--"):
            name, eq, value = token.partition("=")
            if name not in _VALUE_FLAGS:
                return _usage(f"unknown argument {token}")
            if not eq:
                i += 1
                if i >= len(argv):
                    return _usage(f"{name} needs a value")
                value = argv[i]
            opts[name] = value
        elif component_id is not None:
            return _usage(f"unknown argument {token}")
        else:
            component_id = token
        i += 1

    if component_id is None:
        return _usage("missing <component-id>")
    if "--model" not in opts:
        return _usage("missing --model")
    try:
        seed = int(opts.get("--seed", "0"))
    except ValueError:
        return _usage(f"--seed must be an integer, got {opts['--seed']!r}")
    flag_max_attempts = None
    if "--max-attempts" in opts:
        try:
            flag_max_attempts = int(opts["--max-attempts"])
        except ValueError:
            return _usage("--max-attempts must be an integer of at least 1")
        if flag_max_attempts < 1:
            return _usage("--max-attempts must be an integer of at least 1")
    output_format = opts.get("--format", "text")
    if output_format not in _FORMATS:
        return _usage(f"--format must be json or text, got {output_format!r}")
    if "--mode" in opts and opts["--mode"] not in _MODES:
        return _usage(f"--mode must be single or agentic, got {opts['--mode']!r}")

    repo_root = Path(opts["--repo-root"]) if "--repo-root" in opts else Path.cwd()
    slug = _slug(component_id)
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_id.startswith("comp-") or not component_md.is_file():
        return _usage(f"unknown component {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    table = {}
    if toml_path.is_file():
        with open(toml_path, "rb") as fh:
            table = tomllib.load(fh).get("generate", {})
    if "max_attempts" in table:
        value = table["max_attempts"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            return _usage(f"{toml_path}: [generate] max_attempts must be an integer of at least 1")
    if "mode" in table and table["mode"] not in _MODES:
        return _usage(f"{toml_path}: [generate] mode must be single or agentic")
    max_attempts = (
        flag_max_attempts if flag_max_attempts is not None else table.get("max_attempts", 3)
    )
    mode = opts["--mode"] if "--mode" in opts else table.get("mode", "single")

    reauthor = None
    if "--reauthor" in opts:
        ids = opts["--reauthor"].split(",")
        if "" in ids:
            return _usage("--reauthor needs criterion ids")
        frontmatter = re.match(r"\A---\s*\n(.*?)\n---", component_md.read_text(encoding="utf-8"), re.S)
        if frontmatter and re.search(r"^sealed:\s*true\s*$", frontmatter.group(1), re.M):
            return _usage(f"--reauthor does not apply to sealed {component_id}")
        acceptance_dir = repo_root / "specs" / "components" / slug / "acceptance"
        for criterion_id in ids:
            criterion_file = acceptance_dir / f"{criterion_id}.md"
            if (
                not re.fullmatch(r"AC-[A-Za-z0-9-]+", criterion_id)
                or not criterion_file.is_file()
                or "Kind: generated-test"
                not in [line.strip() for line in criterion_file.read_text(encoding="utf-8").splitlines()]
            ):
                return _usage(f"{criterion_id} is not a generated-test criterion of {component_id}")
        reauthor = ids

    retry_feedback = (
        opts["--retry-feedback"].split(",") if "--retry-feedback" in opts else None
    )

    result = run_component_gates(
        component_id,
        repo_root,
        opts["--model"],
        seed,
        None,
        retry_feedback,
        max_attempts=max_attempts,
        mode=mode,
        allow_unisolated_exec=allow_unisolated_exec,
        reauthor=reauthor,
    )

    if output_format == "json":
        print(json.dumps(to_json(result), indent=2))
    else:
        _print_text(result)

    return 1 if _get(result, "block_reason") in _EXIT_ONE_REASONS else 0
