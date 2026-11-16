"""Component Gate Runner: one component's full per-component gauntlet.

`run_component_gates` checks provenance, generates on a miss, verifies,
scans, records the attempt and writes provenance, producing one
`ComponentPipelineResult` dict. `main(argv)` implements `hotdocs generate`.
"""

import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_module(repo_root, slug, module_name):
    """Load a dependency from <repo_root>/gen/<slug>/, else the tool root's."""
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg_dir = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _Deps:
    """Loads each dependency lazily, only when its first call is due."""

    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._loaded = {}

    def load(self, slug, module_name):
        if slug not in self._loaded:
            self._loaded[slug] = _load_module(self._repo_root, slug, module_name)
        return self._loaded[slug]


# ---------------------------------------------------------------------------
# Closures (R-GATE-002, R-GATE-010)
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)\n?```\s*$", re.S)


def _gen_files_text(repo_root, component_id):
    gen_dir = Path(repo_root) / "gen" / _slug(component_id)
    parts = []
    if gen_dir.is_dir():
        for path in sorted(gen_dir.rglob("*")):
            rel = path.relative_to(gen_dir)
            if "__pycache__" in rel.parts or not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"--- FILE: {rel.as_posix()} ---\n{content}\n--- END FILE: {rel.as_posix()} ---")
    return "\n\n".join(parts)


def _judge_prompt(bundle, files_text):
    return (
        "You are judging whether a generated implementation satisfies one "
        "acceptance criterion.\n\n"
        "## Criterion\n"
        f"{_get(bundle, 'criterion_text')}\n\n"
        "## Requirement\n"
        f"{_get(bundle, 'requirement_text')}\n\n"
        "## Interface\n"
        f"{_get(bundle, 'interface')}\n\n"
        "## Implementation files\n"
        f"{files_text}\n\n"
        "Reply with JSON only, exactly of the form "
        '{"result": "pass" | "fail", "rationale": "..."}.'
    )


def _make_judge(deps, component_id, repo_root, model, llm_backend):
    def judge(bundle):
        prompt = _judge_prompt(bundle, _gen_files_text(repo_root, component_id))
        try:
            llm = deps.load("llm-endpoint", "llm_endpoint")
            response = llm.complete(prompt, model, backend=llm_backend)
        except Exception as exc:  # never raised (D166)
            return {"result": "fail", "rationale": f"judge unavailable: {exc}"}
        error = _get(response, "model_call_error")
        if error:
            return {
                "result": "fail",
                "rationale": (
                    "judge unavailable: model_call_error: "
                    f"{_get(error, 'category')}: {_get(error, 'message')}"
                ),
            }
        text = _get(response, "text")
        try:
            stripped = text.strip()
            match = _FENCE_RE.match(stripped)
            if match:
                stripped = match.group(1)
            parsed = json.loads(stripped)
        except (ValueError, TypeError, AttributeError):
            return {"result": "fail", "rationale": "judge unavailable: unparseable response"}
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": f"judge unavailable: invalid result {result!r}"}
        return {"result": result, "rationale": parsed.get("rationale")}

    return judge


def _make_test_author(deps, repo_root, model, seed, llm_backend):
    def test_author(bundle):
        mod = deps.load("test-author", "test_author")
        return mod.author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return test_author


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def _result(component_id, provenance_hit, blocked, block_reason, model_call_error,
            verification, license_scan, secret_scan):
    return {
        "component_id": component_id,
        "provenance_hit": provenance_hit,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": model_call_error,
        "verification": verification,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _scans(deps, component_id, repo_root):
    license_scan = deps.load("license-scanner", "license_scanner").scan(component_id, repo_root)
    secret_scan = deps.load("secret-scanner", "secret_scanner").scan(repo_root)
    return license_scan, secret_scan


def _run_sealed(deps, component_id, repo_root, sealed_key, judge, test_author):
    inputs = {
        "component_id": component_id,
        "owners": _get(sealed_key, "owners"),
        "source_path": _get(sealed_key, "source_path"),
        "source_hash": _get(sealed_key, "source_hash"),
        "verifier_version": _get(sealed_key, "verifier_version"),
    }
    verifier = deps.load("verifier-orchestrator", "verifier_orchestrator")
    report = verifier.verify(component_id, repo_root, judge=judge, test_author=test_author)
    license_scan, secret_scan = _scans(deps, component_id, repo_root)
    inputs["verification_report"] = report
    writer = deps.load("provenance-writer", "provenance_writer")
    writer.write_sealed_provenance(component_id, inputs, repo_root)
    blocked = _get(report, "overall") != "pass"
    return _result(
        component_id, False, blocked,
        "verification_failed" if blocked else None, None,
        report, license_scan, secret_scan,
    )


def run_component_gates(component_id, repo_root, model, seed=0, llm_backend=None,
                        retry_feedback=None):
    deps = _Deps(repo_root)
    judge = _make_judge(deps, component_id, repo_root, model, llm_backend)
    test_author = _make_test_author(deps, repo_root, model, seed, llm_backend)

    checker = deps.load("provenance-checker", "provenance_checker")
    sealed_key = checker.current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(deps, component_id, repo_root, sealed_key, judge, test_author)

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
            component_id, True, False, None, None,
            _get(check, "verification_report"),
            _get(check, "license_scan"),
            _get(check, "secret_scan"),
        )

    assembler = deps.load("spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    generator = deps.load("generator", "generator")
    generation_result = generator.generate(
        bundle, model, retry_feedback, repo_root=repo_root, llm_backend=llm_backend
    )
    files = _get(generation_result, "files")

    report = None
    if files:
        verifier = deps.load("verifier-orchestrator", "verifier_orchestrator")
        report = verifier.verify(component_id, repo_root, judge=judge, test_author=test_author)

    license_scan, secret_scan = _scans(deps, component_id, repo_root)

    try:
        tracker = deps.load("provenance-tracker", "provenance_tracker")
        tracker.write_attempt_record(
            component_id, generation_result, report, spec_bundle_hash, repo_root
        )
    except Exception:
        pass

    if not files:
        return _result(
            component_id, False, True, "model_call_error",
            _get(generation_result, "model_call_error"),
            None, license_scan, secret_scan,
        )

    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / _slug(component_id)
    attempts = (
        sum(1 for p in attempts_dir.iterdir() if p.is_file()) if attempts_dir.is_dir() else 0
    )
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
    writer = deps.load("provenance-writer", "provenance_writer")
    writer.write_provenance(component_id, inputs, repo_root)

    blocked = _get(report, "overall") != "pass"
    return _result(
        component_id, False, blocked,
        "verification_failed" if blocked else None, None,
        report, license_scan, secret_scan,
    )


# ---------------------------------------------------------------------------
# CLI (R-GATE-009)
# ---------------------------------------------------------------------------

_FLAGS = ("--model", "--seed", "--retry-feedback", "--repo-root", "--format")


def _usage(message):
    print(f"usage error: {message}", file=sys.stderr)
    return 2


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if callable(getattr(value, "to_dict", None)):
        return _jsonable(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    return _jsonable(vars(value))


def _text(result):
    lines = [result["component_id"]]
    if result["provenance_hit"]:
        lines.append("provenance hit")
    else:
        lines.append(result["block_reason"] or "passed")
    license_scan = result["license_scan"]
    lines.append(f"license_scan blocked: {_get(license_scan, 'blocked')}")
    lines.append(f"secret_scan flagged: {_get(result['secret_scan'], 'flagged')}")
    error = result["model_call_error"]
    if error:
        lines.append(
            f"model_call_error: {_get(error, 'category')}: {_get(error, 'message')}"
        )
    if _get(license_scan, "evaluated") is False:
        lines.append(f"license_scan not evaluated: {_get(license_scan, 'reason')}")
    return "\n".join(lines)


def main(argv):
    args = list(argv)
    if not args or args[0] != "generate":
        return _usage("expected 'generate' as the first word")

    opts = {}
    positionals = []
    i = 1
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            name, eq, value = arg.partition("=")
            if name not in _FLAGS:
                return _usage(f"unknown argument: {arg}")
            if not eq:
                if i + 1 >= len(args):
                    return _usage(f"{name} requires a value")
                i += 1
                value = args[i]
            opts[name] = value
        else:
            positionals.append(arg)
        i += 1

    if not positionals:
        return _usage("missing <component-id>")
    if len(positionals) > 1:
        return _usage(f"unknown argument: {positionals[1]}")
    component_id = positionals[0]

    if "--model" not in opts:
        return _usage("missing --model")
    model = opts["--model"]

    try:
        seed = int(opts.get("--seed", "0"))
    except ValueError:
        return _usage(f"--seed must be an integer: {opts['--seed']}")

    fmt = opts.get("--format", "text")
    if fmt not in ("json", "text"):
        return _usage(f"invalid --format: {fmt}")

    retry_feedback = (
        opts["--retry-feedback"].split(",") if "--retry-feedback" in opts else None
    )
    repo_root = Path(opts.get("--repo-root", "."))

    if not component_id.startswith("comp-") or not (
        repo_root / "specs" / "components" / _slug(component_id) / "component.md"
    ).is_file():
        return _usage(f"unknown component: {component_id}")

    result = run_component_gates(
        component_id, repo_root, model, seed=seed, llm_backend=None,
        retry_feedback=retry_feedback,
    )

    if fmt == "json":
        print(json.dumps(_jsonable(result), indent=2))
    else:
        print(_text(result))

    return 1 if result["block_reason"] == "model_call_error" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
