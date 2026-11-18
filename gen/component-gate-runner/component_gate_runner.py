"""Component Gate Runner: one component's full per-component gauntlet.

`run_component_gates` runs provenance check, generation on a miss,
verification, both compliance scans, the attempt record, and the
provenance write, returning one `ComponentPipelineResult` dict.
`main(argv)` implements `hotdocs generate`.
"""

import collections.abc
import dataclasses
import enum
import importlib.util
import json
import math
import pathlib
import re
import sys
from pathlib import Path

_MODULE_NAMES = {
    "provenance-checker": "provenance_checker",
    "spec-bundle-assembler": "spec_bundle_assembler",
    "generator": "generator",
    "verifier-orchestrator": "verifier_orchestrator",
    "license-scanner": "license_scanner",
    "secret-scanner": "secret_scanner",
    "provenance-tracker": "provenance_tracker",
    "provenance-writer": "provenance_writer",
    "test-author": "test_author",
    "llm-endpoint": "llm_endpoint",
}

_RESULT_KEYS = (
    "component_id",
    "provenance_hit",
    "blocked",
    "block_reason",
    "model_call_error",
    "verification",
    "license_scan",
    "secret_scan",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, name, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, collections.abc.Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


class _Deps:
    """Loads each dependency from repo_root (else the tool root), lazily."""

    def __init__(self, repo_root):
        self.repo_root = Path(repo_root)
        self.loaded = {}

    def get(self, slug):
        if slug not in self.loaded:
            self.loaded[slug] = self._load(slug)
        return self.loaded[slug]

    def _load(self, slug):
        name = _MODULE_NAMES[slug]
        base = self.repo_root / "gen" / slug
        if not base.is_dir():
            base = _tool_root() / "gen" / slug
        flat = base / f"{name}.py"
        if flat.is_file():
            spec = importlib.util.spec_from_file_location(name, flat)
        else:
            init = base / name / "__init__.py"
            spec = importlib.util.spec_from_file_location(
                name, init, submodule_search_locations=[str(init.parent)]
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module


def _result(component_id, provenance_hit, blocked, block_reason,
            model_call_error, verification, license_scan, secret_scan):
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


# ---------------------------------------------------------------------------
# Closures
# ---------------------------------------------------------------------------


_FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)\n?```$", re.DOTALL)


def _unfence(text):
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _judge_fail(reason):
    return {"result": "fail", "rationale": f"judge unavailable: {reason}"}


def _make_judge(deps, component_id, repo_root, model, llm_backend):
    gen_dir = Path(repo_root) / "gen" / _slug(component_id)

    def judge(bundle):
        parts = [
            "You are judging whether a component's generated code satisfies "
            "one acceptance criterion.",
            "## Criterion\n" + str(_get(bundle, "criterion_text")),
            "## Requirement\n" + str(_get(bundle, "requirement_text")),
            "## Interface\n" + str(_get(bundle, "interface")),
            "## Code",
        ]
        for path in sorted(gen_dir.rglob("*")):
            rel = path.relative_to(gen_dir)
            if "__pycache__" in rel.parts or not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"### {rel.as_posix()}\n{content}")
        parts.append(
            'Reply with only JSON: {"result": "pass" | "fail", "rationale": "..."}'
        )
        prompt = "\n\n".join(parts)
        try:
            response = deps.get("llm-endpoint").complete(
                prompt, model, backend=llm_backend
            )
        except Exception as exc:  # never raised (D166)
            return _judge_fail(str(exc))
        error = _get(response, "model_call_error")
        if error:
            return _judge_fail(
                f"model_call_error: {_get(error, 'category')}: {_get(error, 'message')}"
            )
        try:
            data = json.loads(_unfence(_get(response, "text") or ""))
        except ValueError:
            return _judge_fail("unparseable response")
        result = data.get("result") if isinstance(data, dict) else None
        if result not in ("pass", "fail"):
            return _judge_fail(f"invalid result: {result!r}")
        return {"result": result, "rationale": data.get("rationale")}

    return judge


def _make_test_author(deps, repo_root, model, seed, llm_backend):
    def test_author(bundle):
        return deps.get("test-author").author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return test_author


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def run_component_gates(component_id, repo_root, model, seed=0,
                        llm_backend=None, retry_feedback=None):
    deps = _Deps(repo_root)
    judge = _make_judge(deps, component_id, repo_root, model, llm_backend)
    test_author = _make_test_author(deps, repo_root, model, seed, llm_backend)

    checker = deps.get("provenance-checker")
    sealed_key = checker.current_sealed_key(component_id, repo_root)
    if sealed_key is not None:
        return _run_sealed(deps, component_id, repo_root, sealed_key,
                           judge, test_author)

    key = checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check = checker.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root
    )
    hit_report = _get(check, "verification_report")
    hit_license = _get(check, "license_scan")
    if (
        _get(check, "hit")
        and _get(hit_report, "overall") == "pass"
        and _get(hit_license, "blocked") is not True
    ):
        return _result(component_id, True, False, None, None,
                       hit_report, hit_license, _get(check, "secret_scan"))

    bundle = deps.get("spec-bundle-assembler").assemble(
        component_id, repo_root=repo_root, mode="cold"
    )
    generation = deps.get("generator").generate(
        bundle, model, retry_feedback, repo_root=repo_root, llm_backend=llm_backend
    )
    files = _get(generation, "files")

    report = None
    if files:
        report = deps.get("verifier-orchestrator").verify(
            component_id, repo_root, judge=judge, test_author=test_author
        )

    license_scan = deps.get("license-scanner").scan(component_id, repo_root)
    secret_scan = deps.get("secret-scanner").scan(repo_root)

    try:
        deps.get("provenance-tracker").write_attempt_record(
            component_id, generation, report, spec_bundle_hash, repo_root
        )
    except Exception:
        pass

    if files:
        attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / _slug(component_id)
        attempts = 0
        if attempts_dir.is_dir():
            attempts = sum(1 for p in attempts_dir.iterdir() if p.is_file())
        inputs = {
            "component_id": component_id,
            "generation_result": generation,
            "verification_report": report,
            "license_scan_result": license_scan,
            "secret_scan_result": secret_scan,
            "provenance_hit": False,
            "attempts": attempts,
            "gate_versions": gate_versions,
        }
        deps.get("provenance-writer").write_provenance(component_id, inputs, repo_root)

    if not files:
        return _result(component_id, False, True, "model_call_error",
                       _get(generation, "model_call_error"), None,
                       license_scan, secret_scan)
    if _get(report, "overall") == "pass":
        return _result(component_id, False, False, None, None,
                       report, license_scan, secret_scan)
    failed = [c for c in (_get(report, "criteria") or []) if _get(c, "result") == "fail"]
    if failed and all(_get(c, "failure_origin") == "test" for c in failed):
        reason = "test_authoring_failed"
    else:
        reason = "verification_failed"
    return _result(component_id, False, True, reason, None,
                   report, license_scan, secret_scan)


def _run_sealed(deps, component_id, repo_root, sealed_key, judge, test_author):
    owners = _get(sealed_key, "owners")
    source_path = _get(sealed_key, "source_path")
    source_hash = _get(sealed_key, "source_hash")
    verifier_version = _get(sealed_key, "verifier_version")

    report = deps.get("verifier-orchestrator").verify(
        component_id, repo_root, judge=judge, test_author=test_author
    )
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
    deps.get("provenance-writer").write_sealed_provenance(
        component_id, inputs, repo_root
    )

    if _get(report, "overall") == "pass":
        return _result(component_id, False, False, None, None,
                       report, license_scan, secret_scan)
    return _result(component_id, False, True, "verification_failed", None,
                   report, license_scan, secret_scan)


# ---------------------------------------------------------------------------
# JSON conversion (specs/architecture/json-values.md)
# ---------------------------------------------------------------------------


def to_json(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, collections.abc.Mapping):
        return {
            (k if isinstance(k, str) else str(k)): to_json(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(v) for v in value]
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
            f.name: to_json(getattr(value, f.name))
            for f in dataclasses.fields(value)
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
# ---------------------------------------------------------------------------


_FLAGS = ("--model", "--seed", "--retry-feedback", "--repo-root", "--format")


class _UsageError(Exception):
    pass


def _parse(argv):
    if not argv or argv[0] != "generate":
        raise _UsageError("expected first word 'generate'")
    values = {}
    positionals = []
    args = list(argv[1:])
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            flag, eq, val = arg.partition("=")
            if flag not in _FLAGS:
                raise _UsageError(f"unknown argument: {arg}")
            if not eq:
                if i + 1 >= len(args):
                    raise _UsageError(f"{flag} given with no value")
                i += 1
                val = args[i]
            values[flag] = val
        else:
            positionals.append(arg)
        i += 1
    if not positionals:
        raise _UsageError("missing <component-id>")
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument: {positionals[1]}")
    if "--model" not in values:
        raise _UsageError("missing --model")
    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {values['--seed']}")
    fmt = values.get("--format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")
    component_id = positionals[0]
    repo_root = Path(values.get("--repo-root", "."))
    component_md = repo_root / "specs" / "components" / _slug(component_id) / "component.md"
    if not component_md.is_file():
        raise _UsageError(f"unknown component: {component_id}")
    retry = values.get("--retry-feedback")
    return {
        "component_id": component_id,
        "repo_root": repo_root,
        "model": values["--model"],
        "seed": seed,
        "retry_feedback": retry.split(",") if retry is not None else None,
        "format": fmt,
    }


def _text_lines(result):
    lines = [result["component_id"]]
    if result["provenance_hit"]:
        lines.append("provenance hit")
    else:
        lines.append(result["block_reason"] or "passed")
    license_scan = result["license_scan"]
    secret_scan = result["secret_scan"]
    verification = result["verification"]
    lines.append(f"license_scan.blocked: {_get(license_scan, 'blocked')}")
    lines.append(f"secret_scan.flagged: {_get(secret_scan, 'flagged')}")
    error = result["model_call_error"]
    if error:
        lines.append(
            f"model_call_error: {_get(error, 'category')}: {_get(error, 'message')}"
        )
    if result["block_reason"] == "test_authoring_failed":
        for c in _get(verification, "criteria") or []:
            if _get(c, "result") == "fail":
                detail = _get(c, "failure_detail")
                lines.append(f"{_get(c, 'id')}: {_get(detail, 'message')}")
    mutation_error = _get(verification, "mutation_error")
    if mutation_error:
        lines.append(f"mutation_error: {mutation_error}")
    if _get(license_scan, "evaluated") is False:
        lines.append(f"license_scan not evaluated: {_get(license_scan, 'reason')}")
    return lines


def main(argv):
    try:
        args = _parse(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    result = run_component_gates(
        args["component_id"],
        args["repo_root"],
        args["model"],
        seed=args["seed"],
        retry_feedback=args["retry_feedback"],
    )
    if args["format"] == "json":
        print(json.dumps(to_json(result), indent=2))
    else:
        print("\n".join(_text_lines(result)))
    if result["block_reason"] in ("model_call_error", "test_authoring_failed"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
