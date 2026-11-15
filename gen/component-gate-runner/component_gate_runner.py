"""Component Gate Runner: one component's full per-component gauntlet.

Provenance check, generation on a miss, verification dispatch, compliance
scanning, attempt record and provenance write, producing one
``ComponentPipelineResult`` (R-GATE-001..010). ``main(argv)`` implements
``hotdocs generate`` (R-GATE-009).
"""

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

__all__ = ["run_component_gates", "main"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, key):
    """Dual dict-or-attribute access for every dependency value."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _tool_root():
    """The parent of the nearest directory named ``gen`` above this file."""
    gen_dir = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen_dir.parent


def _load_dependency(repo_root, slug, module_name):
    """Load ``module_name`` from ``<repo_root>/gen/<slug>/``, else the tool root's."""
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        package_dir = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _gen_files_text(repo_root, component_id):
    """Full text of every file under ``gen/<slug>/``, skipping ``__pycache__``."""
    base = Path(repo_root) / "gen" / _slug(component_id)
    parts = []
    for path in sorted(base.rglob("*")):
        if "__pycache__" in path.relative_to(base).parts or not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        parts.append(f"--- {rel} ---\n{text}")
    return "\n\n".join(parts)


_FENCE_RE = re.compile(r"^```[A-Za-z0-9_-]*[ \t]*\n(.*?)\n?```\s*$", re.DOTALL)


def _unwrap_fence(text):
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1)
    return stripped


def _judge_prompt(bundle, files_text):
    return (
        "You are judging whether a component's generated code satisfies one "
        "acceptance criterion.\n\n"
        "## Criterion\n\n"
        f"{_get(bundle, 'criterion_text')}\n\n"
        "## Requirement\n\n"
        f"{_get(bundle, 'requirement_text')}\n\n"
        "## Interface\n\n"
        f"{_get(bundle, 'interface')}\n\n"
        "## Generated code\n\n"
        f"{files_text}\n\n"
        "Reply with JSON only, exactly of the form "
        '{"result": "pass" | "fail", "rationale": "..."}.'
    )


def _judge_unavailable(reason):
    return {"result": "fail", "rationale": f"judge unavailable: {reason}"}


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
):
    """Run one component through its gauntlet; return a ComponentPipelineResult dict."""
    modules = {}

    def dep(slug, module_name):
        if module_name not in modules:
            modules[module_name] = _load_dependency(repo_root, slug, module_name)
        return modules[module_name]

    def test_author_closure(bundle):
        test_author = dep("test-author", "test_author")
        return test_author.author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    def judge_closure(bundle):
        try:
            llm_endpoint = dep("llm-endpoint", "llm_endpoint")
            prompt = _judge_prompt(bundle, _gen_files_text(repo_root, component_id))
            response = llm_endpoint.complete(prompt, model, backend=llm_backend)
        except Exception as exc:  # never raised (D166)
            return _judge_unavailable(f"{type(exc).__name__}: {exc}")
        error = _get(response, "model_call_error")
        if error:
            return _judge_unavailable(
                f"model_call_error: {_get(error, 'category')}: {_get(error, 'message')}"
            )
        try:
            parsed = json.loads(_unwrap_fence(_get(response, "text")))
        except Exception:
            return _judge_unavailable("unparseable response")
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if result not in ("pass", "fail"):
            return _judge_unavailable(f"invalid result: {result!r}")
        return {"result": result, "rationale": parsed.get("rationale")}

    checker = dep("provenance-checker", "provenance_checker")
    sealed_key = checker.current_sealed_key(component_id, repo_root)

    if sealed_key is not None:
        owners = _get(sealed_key, "owners")
        source_path = _get(sealed_key, "source_path")
        source_hash = _get(sealed_key, "source_hash")
        verifier_version = _get(sealed_key, "verifier_version")

        verifier = dep("verifier-orchestrator", "verifier_orchestrator")
        report = verifier.verify(
            component_id, repo_root, judge=judge_closure, test_author=test_author_closure
        )
        license_scan = dep("license-scanner", "license_scanner").scan(component_id, repo_root)
        secret_scan = dep("secret-scanner", "secret_scanner").scan(repo_root)

        sealed_inputs = {
            "component_id": component_id,
            "owners": owners,
            "source_path": source_path,
            "source_hash": source_hash,
            "verifier_version": verifier_version,
            "verification_report": report,
        }
        dep("provenance-writer", "provenance_writer").write_sealed_provenance(
            component_id, sealed_inputs, repo_root
        )

        blocked = _get(report, "overall") != "pass"
        return {
            "component_id": component_id,
            "provenance_hit": False,
            "blocked": blocked,
            "block_reason": "verification_failed" if blocked else None,
            "model_call_error": None,
            "verification": report,
            "license_scan": license_scan,
            "secret_scan": secret_scan,
        }

    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = checker.check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)

    if (
        _get(check, "hit")
        and _get(_get(check, "verification_report"), "overall") == "pass"
        and _get(_get(check, "license_scan"), "blocked") is not True
    ):
        return {
            "component_id": component_id,
            "provenance_hit": True,
            "blocked": False,
            "block_reason": None,
            "model_call_error": None,
            "verification": _get(check, "verification_report"),
            "license_scan": _get(check, "license_scan"),
            "secret_scan": _get(check, "secret_scan"),
        }

    bundle = dep("spec-bundle-assembler", "spec_bundle_assembler").assemble(
        component_id, repo_root=repo_root, mode="cold"
    )
    generation_result = dep("generator", "generator").generate(
        bundle, model, retry_feedback, repo_root=repo_root, llm_backend=llm_backend
    )
    files = _get(generation_result, "files")

    report = None
    if files:
        verifier = dep("verifier-orchestrator", "verifier_orchestrator")
        report = verifier.verify(
            component_id, repo_root, judge=judge_closure, test_author=test_author_closure
        )

    license_scan = dep("license-scanner", "license_scanner").scan(component_id, repo_root)
    secret_scan = dep("secret-scanner", "secret_scanner").scan(repo_root)

    try:
        dep("provenance-tracker", "provenance_tracker").write_attempt_record(
            component_id, generation_result, report, spec_bundle_hash, repo_root
        )
    except Exception:
        pass  # R-GATE-008: never changes this component's result

    if files:
        attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / _slug(component_id)
        attempts = 0
        if attempts_dir.is_dir():
            attempts = sum(1 for p in attempts_dir.iterdir() if p.is_file())
        inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": report,
            "license_scan_result": license_scan,
            "secret_scan_result": secret_scan,
            "provenance_hit": False,
            "attempts": attempts,
            "gate_versions": gate_versions,
        }
        dep("provenance-writer", "provenance_writer").write_provenance(
            component_id, inputs, repo_root
        )
        blocked = _get(report, "overall") != "pass"
        return {
            "component_id": component_id,
            "provenance_hit": False,
            "blocked": blocked,
            "block_reason": "verification_failed" if blocked else None,
            "model_call_error": None,
            "verification": report,
            "license_scan": license_scan,
            "secret_scan": secret_scan,
        }

    return {
        "component_id": component_id,
        "provenance_hit": False,
        "blocked": True,
        "block_reason": "model_call_error",
        "model_call_error": _get(generation_result, "model_call_error"),
        "verification": None,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_USAGE = (
    "usage: hotdocs generate <component-id> --model=<model-id> [--seed=<n>] "
    "[--retry-feedback=<R-id>,...] [--repo-root=<dir>] [--format=json|text]"
)

_FLAGS = ("--model", "--seed", "--retry-feedback", "--repo-root", "--format")


class _UsageError(Exception):
    pass


def _parse_args(argv):
    if not argv or argv[0] != "generate":
        raise _UsageError("expected 'generate' as the first word")
    args = argv[1:]
    opts = {}
    positional = []
    i = 0
    while i < len(args):
        arg = args[i]
        name, eq, value = arg.partition("=")
        if name in _FLAGS:
            if not eq:
                if i + 1 >= len(args):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                value = args[i]
            opts[name] = value
        elif arg.startswith("-") or positional:
            raise _UsageError(f"unknown argument: {arg}")
        else:
            positional.append(arg)
        i += 1

    if not positional:
        raise _UsageError("missing <component-id>")
    if "--model" not in opts:
        raise _UsageError("missing --model")
    try:
        seed = int(opts.get("--seed", "0"))
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {opts['--seed']}")
    fmt = opts.get("--format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")
    retry_feedback = None
    if "--retry-feedback" in opts:
        retry_feedback = opts["--retry-feedback"].split(",")
    repo_root = Path(opts.get("--repo-root", "."))
    component_id = positional[0]
    component_md = repo_root / "specs" / "components" / _slug(component_id) / "component.md"
    if not component_md.is_file():
        raise _UsageError(f"unknown component: {component_id}")
    return component_id, opts["--model"], seed, retry_feedback, repo_root, fmt


def _to_jsonable(value):
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if callable(getattr(value, "to_dict", None)):
        return _to_jsonable(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(dataclasses.asdict(value))
    return _to_jsonable(vars(value))


def _print_text(result):
    print(result["component_id"])
    if result["provenance_hit"]:
        print("provenance hit")
    else:
        print(result["block_reason"] or "passed")
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    print(f"license_scan blocked: {_get(license_scan, 'blocked')}")
    print(f"secret_scan flagged: {_get(secret_scan, 'flagged')}")
    error = result["model_call_error"]
    if error:
        print(f"model_call_error: {_get(error, 'category')}: {_get(error, 'message')}")
    if _get(license_scan, "evaluated") is False:
        print(f"license_scan not evaluated: {_get(license_scan, 'reason')}")


def main(argv):
    """``hotdocs generate``; returns the exit code (0, 1 or 2)."""
    try:
        component_id, model, seed, retry_feedback, repo_root, fmt = _parse_args(list(argv))
    except _UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2

    result = run_component_gates(
        component_id, repo_root, model, seed=seed, retry_feedback=retry_feedback
    )

    if fmt == "json":
        print(json.dumps(_to_jsonable(result), indent=2))
    else:
        _print_text(result)

    if _get(result, "block_reason") == "model_call_error":
        return 1
    return 0
