"""Component Gate Runner: runs one component through its gauntlet.

`run_component_gates` sequences provenance check, generation (through
`generation-loop`), verification, compliance scans and provenance write;
`main` implements `hotdocs generate`.
"""

from __future__ import annotations

import dataclasses
import enum
import importlib.util
import itertools
import json
import math
import pathlib
import re
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

__all__ = ["run_component_gates", "main"]

_LOAD_COUNTER = itertools.count()

_REVERIFY_REASONS = ("environment differs", "dependency code differs")

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


# ---------------------------------------------------------------------------
# helpers


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_dependency(slug: str, repo_root) -> object:
    module = slug.replace("-", "_")
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module}.py"
    name = f"_cgr_{module}_{next(_LOAD_COUNTER)}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Deps:
    """Loads each dependency afresh per run, on its first use."""

    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._mods = {}

    def __call__(self, slug: str):
        if slug not in self._mods:
            self._mods[slug] = _load_dependency(slug, self._repo_root)
        return self._mods[slug]


def _slug(component_id: str) -> str:
    return component_id.removeprefix("comp-")


def _result(component_id, **fields) -> dict:
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


def _is_short_circuit(check) -> bool:
    return (
        _get(check, "hit") is True
        and _get(_get(check, "verification_report"), "overall") == "pass"
        and _get(_get(check, "license_scan"), "blocked") is not True
    )


def _delete_reauthor(component_id, repo_root, reauthor) -> None:
    if reauthor is None:
        return
    base = Path(repo_root) / "verification" / _slug(component_id) / "generated-test"
    for cid in reauthor:
        target = base / f"test_{cid.lower().replace('-', '_')}.py"
        if target.exists():
            target.unlink()


def _count_attempt_files(component_id, repo_root) -> int:
    d = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not d.is_dir():
        return 0
    return sum(1 for p in d.iterdir() if p.is_file())


def _test_authoring_failed(report) -> bool:
    failing = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    return bool(failing) and all(_get(c, "failure_origin") == "test" for c in failing)


# ---------------------------------------------------------------------------
# library


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

    failed = _get(report, "overall") == "fail"
    return _result(
        component_id,
        blocked=failed,
        block_reason="verification_failed" if failed else None,
        verification=report,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


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
    reauthor: list[str] | None = None,
) -> dict:
    deps = _Deps(repo_root)
    checker = deps("provenance-checker")

    sealed_key = checker.current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(component_id, repo_root, model, seed, llm_backend, sealed_key, deps)

    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    spec_bundle_parts = _get(key, "spec_bundle_parts")

    check = checker.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts
    )
    if _is_short_circuit(check):
        return _result(
            component_id,
            provenance_hit=True,
            verification=_get(check, "verification_report"),
            license_scan=_get(check, "license_scan"),
            secret_scan=_get(check, "secret_scan"),
        )

    _delete_reauthor(component_id, repo_root, reauthor)

    if _get(check, "reason") in _REVERIFY_REASONS:
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
                component_id, generation_result, verification_report, spec_bundle_hash, repo_root
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
            "attempts": _count_attempt_files(component_id, repo_root),
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
        elif _test_authoring_failed(verification_report):
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


# ---------------------------------------------------------------------------
# JSON conversion (specs/architecture/json-values.md)


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
        return sorted(items, key=lambda i: json.dumps(i, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, pathlib.PurePath):
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


# ---------------------------------------------------------------------------
# CLI


def _usage(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def _parse_int(text):
    try:
        return int(text)
    except ValueError:
        return None


def _frontmatter_sealed(component_md: Path) -> bool:
    lines = component_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        name, sep, val = line.partition(":")
        if sep and name.strip() == "sealed" and val.strip() == "true":
            return True
    return False


def _is_generated_test_criterion(acceptance_dir: Path, cid: str) -> bool:
    if not re.fullmatch(r"AC-[A-Za-z0-9-]+", cid):
        return False
    path = acceptance_dir / f"{cid}.md"
    if not path.is_file():
        return False
    return any(
        line.strip() == "Kind: generated-test"
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _print_text(result: dict) -> None:
    component_id = result["component_id"]
    if result["provenance_hit"]:
        status = "provenance hit"
    elif result["reverified"]:
        status = "reverified"
    else:
        status = result["block_reason"] or "passed"
    print(f"{component_id}: {status}")
    for attempt in result["attempts"] or []:
        print(f"attempt {_get(attempt, 'number')}: {_get(attempt, 'outcome')}")
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    print(f"license_scan blocked: {json.dumps(_to_json(_get(license_scan, 'blocked')))}")
    print(f"secret_scan flagged: {json.dumps(_to_json(_get(secret_scan, 'flagged')))}")
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
    if mutation_error is not None:
        print(f"mutation_error: {mutation_error}")
    if _get(license_scan, "evaluated") is False:
        print(f"license_scan not evaluated: {_get(license_scan, 'reason')}")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "generate":
        return _usage("expected first word generate")

    values: dict[str, str] = {}
    positionals: list[str] = []
    allow_unisolated_exec = False
    i = 1
    while i < len(args):
        token = args[i]
        name, eq, val = token.partition("=")
        if name in _VALUE_FLAGS:
            if not eq:
                if i + 1 >= len(args):
                    return _usage(f"{name} needs a value")
                i += 1
                val = args[i]
            values[name] = val
        elif token == "--allow-unisolated-exec":
            allow_unisolated_exec = True
        elif token.startswith("-") or positionals:
            return _usage(f"unknown argument {token}")
        else:
            positionals.append(token)
        i += 1

    if not positionals:
        return _usage("missing <component-id>")
    component_id = positionals[0]
    if "--model" not in values:
        return _usage("missing --model")
    model = values["--model"]

    seed = 0
    if "--seed" in values:
        seed = _parse_int(values["--seed"])
        if seed is None:
            return _usage(f"--seed must be an integer: {values['--seed']}")

    flag_max_attempts = None
    if "--max-attempts" in values:
        flag_max_attempts = _parse_int(values["--max-attempts"])
        if flag_max_attempts is None or flag_max_attempts < 1:
            return _usage(
                f"--max-attempts must be an integer of at least 1: {values['--max-attempts']}"
            )

    flag_mode = values.get("--mode")
    if flag_mode is not None and flag_mode not in ("single", "agentic"):
        return _usage(f"--mode must be single or agentic: {flag_mode}")

    output_format = values.get("--format", "text")
    if output_format not in ("json", "text"):
        return _usage(f"--format must be json or text: {output_format}")

    repo_root = Path(values.get("--repo-root", "."))
    slug = _slug(component_id)
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_id.startswith("comp-") or not component_md.is_file():
        return _usage(f"unknown component {component_id}")

    toml_path = repo_root / "hotdocs.toml"
    generate_cfg = {}
    if toml_path.is_file():
        with open(toml_path, "rb") as fh:
            generate_cfg = tomllib.load(fh).get("generate", {})

    file_max_attempts = None
    if "max_attempts" in generate_cfg:
        file_max_attempts = generate_cfg["max_attempts"]
        if (
            not isinstance(file_max_attempts, int)
            or isinstance(file_max_attempts, bool)
            or file_max_attempts < 1
        ):
            return _usage(
                f"{toml_path}: [generate] max_attempts must be an integer of at least 1"
            )
    file_mode = None
    if "mode" in generate_cfg:
        file_mode = generate_cfg["mode"]
        if file_mode not in ("single", "agentic"):
            return _usage(f"{toml_path}: [generate] mode must be single or agentic")

    if flag_max_attempts is not None:
        max_attempts = flag_max_attempts
    elif file_max_attempts is not None:
        max_attempts = file_max_attempts
    else:
        max_attempts = 3

    if flag_mode is not None:
        mode = flag_mode
    elif file_mode is not None:
        mode = file_mode
    else:
        mode = "single"

    retry_feedback = None
    if "--retry-feedback" in values:
        retry_feedback = values["--retry-feedback"].split(",")

    reauthor = None
    if "--reauthor" in values:
        reauthor = values["--reauthor"].split(",")
        if any(entry == "" for entry in reauthor):
            return _usage("--reauthor needs criterion ids")
        if _frontmatter_sealed(component_md):
            return _usage(f"--reauthor does not apply to sealed {component_id}")
        acceptance_dir = repo_root / "specs" / "components" / slug / "acceptance"
        for cid in reauthor:
            if not _is_generated_test_criterion(acceptance_dir, cid):
                return _usage(f"{cid} is not a generated-test criterion of {component_id}")

    result = run_component_gates(
        component_id,
        repo_root,
        model,
        seed=seed,
        retry_feedback=retry_feedback,
        max_attempts=max_attempts,
        mode=mode,
        allow_unisolated_exec=allow_unisolated_exec,
        reauthor=reauthor,
    )

    if output_format == "json":
        print(json.dumps(_to_json(result)))
    else:
        _print_text(result)

    if _get(result, "block_reason") in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0
