"""Component Gate Runner (comp-component-gate-runner).

Runs one component through its full per-component gauntlet: provenance
check, generation on a miss, verification dispatch, compliance scanning,
provenance write.
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


# ---------------------------------------------------------------------------
# Dynamic dependency loading
# ---------------------------------------------------------------------------

def _load_module_from_path(load_name, module_path, is_package):
    import importlib.util

    search_locations = [str(module_path.parent)] if is_package else None
    spec = importlib.util.spec_from_file_location(
        load_name, module_path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec_module: required so dataclasses
    # defined in the loaded module can resolve sys.modules[cls.__module__]
    # while their class bodies execute.
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


def _load_module(repo_root, slug, source_path=None):
    name = slug.replace("-", "_")
    if source_path is not None:
        base = Path(repo_root) / source_path
    else:
        base = Path(repo_root) / "gen" / slug

    pkg_init = base / name / "__init__.py"
    flat = base / f"{name}.py"
    if pkg_init.exists():
        module_path = pkg_init
        is_package = True
    elif flat.exists():
        module_path = flat
        is_package = False
    else:
        raise ImportError(f"cannot locate module '{name}' under {base}")

    load_name = f"_hotdocs_component_gate_runner_dep_{name}"
    return _load_module_from_path(load_name, module_path, is_package)


def _get_module(loaded, repo_root, slug):
    if slug not in loaded:
        loaded[slug] = _load_module(repo_root, slug)
    return loaded[slug]


# ---------------------------------------------------------------------------
# judge closure (R-GATE-010)
# ---------------------------------------------------------------------------

def _unwrap_code_fence(text):
    stripped = text.strip()
    match = re.match(r"^```[a-zA-Z0-9_+-]*\s*\n(.*?)\n```$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _collect_gen_files_text(repo_root, slug):
    base = Path(repo_root) / "gen" / slug
    parts = []
    if base.exists():
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue
            rel = path.relative_to(base)
            parts.append(f"--- {rel} ---\n{content}")
    return "\n\n".join(parts)


def _build_judge_prompt(criterion_text, requirement_text, interface_text, files_text):
    return (
        "You are judging whether generated source code satisfies an "
        "acceptance criterion.\n\n"
        f"Criterion:\n{criterion_text}\n\n"
        f"Requirement:\n{requirement_text}\n\n"
        f"Interface:\n{interface_text}\n\n"
        f"Generated files:\n{files_text}\n\n"
        'Respond with JSON only, of the exact shape '
        '{"result": "pass" | "fail", "rationale": "..."}'
    )


def _make_judge_closure(repo_root, model, llm_backend, loaded):
    def judge_closure(bundle):
        criterion_text = _get(bundle, "criterion_text", "")
        requirement_text = _get(bundle, "requirement_text", "")
        interface_text = _get(bundle, "interface", "")
        bundle_component_id = _get(bundle, "component_id", "")
        slug = _slug(bundle_component_id)
        files_text = _collect_gen_files_text(repo_root, slug)
        prompt = _build_judge_prompt(
            criterion_text, requirement_text, interface_text, files_text
        )

        try:
            llm_endpoint = _get_module(loaded, repo_root, "llm-endpoint")
            response = llm_endpoint.complete(prompt, model, backend=llm_backend)
        except Exception as exc:
            return {"result": "fail", "rationale": f"judge unavailable: {exc}"}

        model_call_error = _get(response, "model_call_error")
        if model_call_error:
            message = _get(model_call_error, "message") or _get(
                model_call_error, "category"
            ) or "model call error"
            return {"result": "fail", "rationale": f"judge unavailable: {message}"}

        text = _get(response, "text")
        if text is None:
            return {"result": "fail", "rationale": "judge unavailable: empty response"}

        unwrapped = _unwrap_code_fence(text)
        try:
            parsed = json.loads(unwrapped)
        except Exception as exc:
            return {
                "result": "fail",
                "rationale": f"judge unavailable: unparseable response ({exc})",
            }

        if not isinstance(parsed, dict):
            return {
                "result": "fail",
                "rationale": "judge unavailable: unparseable response",
            }

        result = parsed.get("result")
        rationale = parsed.get("rationale")
        if result not in ("pass", "fail"):
            return {
                "result": "fail",
                "rationale": f"judge unavailable: invalid result {result!r}",
            }
        return {"result": result, "rationale": rationale}

    return judge_closure


def _make_test_author_closure(repo_root, model, seed, llm_backend, loaded):
    def test_author_closure(bundle):
        test_author = _get_module(loaded, repo_root, "test-author")
        return test_author.author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return test_author_closure


# ---------------------------------------------------------------------------
# Attempt counting (for ProvenanceInputs.attempts)
# ---------------------------------------------------------------------------

def _count_attempts(repo_root, component_id):
    slug = _slug(component_id)
    directory = Path(repo_root) / ".hotdocs" / "attempts" / slug
    if not directory.exists():
        return 0
    return len([p for p in directory.iterdir() if p.is_file()])


# ---------------------------------------------------------------------------
# Core entry point
# ---------------------------------------------------------------------------

def run_component_gates(
    component_id: str,
    repo_root: Path,
    model: str,
    seed: int = 0,
    llm_backend=None,
    retry_feedback=None,
) -> dict:
    loaded = {}

    provenance_checker = _get_module(loaded, repo_root, "provenance-checker")
    sealed_key = provenance_checker.current_sealed_key(component_id, repo_root)

    if sealed_key is not None:
        return _run_sealed(
            component_id, repo_root, model, seed, llm_backend, loaded, sealed_key
        )

    return _run_generated(
        component_id,
        repo_root,
        model,
        seed,
        llm_backend,
        retry_feedback,
        loaded,
        provenance_checker,
    )


def _run_sealed(component_id, repo_root, model, seed, llm_backend, loaded, sealed_key):
    verifier_orchestrator = _get_module(loaded, repo_root, "verifier-orchestrator")
    judge_closure = _make_judge_closure(repo_root, model, llm_backend, loaded)
    test_author_closure = _make_test_author_closure(
        repo_root, model, seed, llm_backend, loaded
    )

    verification_report = verifier_orchestrator.verify(
        component_id, repo_root, judge=judge_closure, test_author=test_author_closure
    )

    license_scanner = _get_module(loaded, repo_root, "license-scanner")
    secret_scanner = _get_module(loaded, repo_root, "secret-scanner")
    license_scan = license_scanner.scan(component_id, repo_root)
    secret_scan = secret_scanner.scan(repo_root)

    provenance_writer = _get_module(loaded, repo_root, "provenance-writer")
    sealed_inputs = {
        "component_id": component_id,
        "owners": _get(sealed_key, "owners"),
        "source_path": _get(sealed_key, "source_path"),
        "source_hash": _get(sealed_key, "source_hash"),
        "verifier_version": _get(sealed_key, "verifier_version"),
        "verification_report": verification_report,
    }
    provenance_writer.write_sealed_provenance(component_id, sealed_inputs, repo_root)

    overall = _get(verification_report, "overall")
    blocked = overall != "pass"

    return {
        "component_id": component_id,
        "provenance_hit": False,
        "blocked": blocked,
        "block_reason": "verification_failed" if blocked else None,
        "model_call_error": None,
        "verification": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _run_generated(
    component_id,
    repo_root,
    model,
    seed,
    llm_backend,
    retry_feedback,
    loaded,
    provenance_checker,
):
    key = provenance_checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")

    check_result = provenance_checker.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root
    )

    hit = _get(check_result, "hit")
    hit_verification = _get(check_result, "verification_report")
    hit_license_scan = _get(check_result, "license_scan")
    hit_secret_scan = _get(check_result, "secret_scan")

    hit_overall = _get(hit_verification, "overall") if hit_verification is not None else None
    hit_license_blocked = (
        _get(hit_license_scan, "blocked") if hit_license_scan is not None else None
    )

    if hit and hit_overall == "pass" and hit_license_blocked is not True:
        return {
            "component_id": component_id,
            "provenance_hit": True,
            "blocked": False,
            "block_reason": None,
            "model_call_error": None,
            "verification": hit_verification,
            "license_scan": hit_license_scan,
            "secret_scan": hit_secret_scan,
        }

    # Miss: assemble, generate once.
    spec_bundle_assembler = _get_module(loaded, repo_root, "spec-bundle-assembler")
    bundle = spec_bundle_assembler.assemble(component_id, repo_root=repo_root, mode="cold")

    generator = _get_module(loaded, repo_root, "generator")
    generation_result = generator.generate(
        bundle, model, retry_feedback, repo_root=repo_root, llm_backend=llm_backend
    )

    files = _get(generation_result, "files")
    verification_report = None
    if files:
        verifier_orchestrator = _get_module(loaded, repo_root, "verifier-orchestrator")
        judge_closure = _make_judge_closure(repo_root, model, llm_backend, loaded)
        test_author_closure = _make_test_author_closure(
            repo_root, model, seed, llm_backend, loaded
        )
        verification_report = verifier_orchestrator.verify(
            component_id,
            repo_root,
            judge=judge_closure,
            test_author=test_author_closure,
        )

    license_scanner = _get_module(loaded, repo_root, "license-scanner")
    secret_scanner = _get_module(loaded, repo_root, "secret-scanner")
    license_scan = license_scanner.scan(component_id, repo_root)
    secret_scan = secret_scanner.scan(repo_root)

    provenance_tracker = _get_module(loaded, repo_root, "provenance-tracker")
    try:
        provenance_tracker.write_attempt_record(
            component_id, generation_result, verification_report, spec_bundle_hash, repo_root
        )
    except Exception:
        pass

    model_call_error = _get(generation_result, "model_call_error")

    if not files:
        blocked = True
        block_reason = "model_call_error"
    else:
        overall = _get(verification_report, "overall")
        if overall == "pass":
            blocked = False
            block_reason = None
        else:
            blocked = True
            block_reason = "verification_failed"

    if files:
        provenance_writer = _get_module(loaded, repo_root, "provenance-writer")
        attempts = _count_attempts(repo_root, component_id)
        provenance_inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": license_scan,
            "secret_scan_result": secret_scan,
            "provenance_hit": False,
            "attempts": attempts,
            "gate_versions": gate_versions,
        }
        provenance_writer.write_provenance(component_id, provenance_inputs, repo_root)

    return {
        "component_id": component_id,
        "provenance_hit": False,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": model_call_error if block_reason == "model_call_error" else None,
        "verification": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _to_jsonable(value):
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _to_jsonable(to_dict())
    if dataclasses.is_dataclass(value):
        return _to_jsonable(dataclasses.asdict(value))
    try:
        return _to_jsonable(vars(value))
    except TypeError:
        return str(value)


def _print_text(result):
    component_id = _get(result, "component_id")
    provenance_hit = _get(result, "provenance_hit")
    blocked = _get(result, "blocked")
    block_reason = _get(result, "block_reason")
    model_call_error = _get(result, "model_call_error")
    license_scan = _get(result, "license_scan")
    secret_scan = _get(result, "secret_scan")

    print(component_id)
    if provenance_hit:
        print("provenance hit")
    else:
        print(block_reason if blocked else "passed")

    license_blocked = _get(license_scan, "blocked") if license_scan is not None else None
    secret_flagged = _get(secret_scan, "flagged") if secret_scan is not None else None
    print(f"license_scan blocked: {license_blocked}")
    print(f"secret_scan flagged: {secret_flagged}")

    if model_call_error:
        category = _get(model_call_error, "category")
        message = _get(model_call_error, "message")
        print(f"model_call_error: {category}: {message}")

    evaluated = _get(license_scan, "evaluated") if license_scan is not None else None
    if evaluated is False:
        reason = _get(license_scan, "reason")
        print(f"license_scan not evaluated: {reason}")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)

    if not args or args[0] != "generate":
        print("usage error: expected 'generate' as the first argument", file=sys.stderr)
        return 2
    args = args[1:]

    model = None
    seed = 0
    retry_feedback = None
    repo_root = Path(".")
    fmt = "text"
    positional = []

    i = 0
    known_flags = {"--model", "--seed", "--retry-feedback", "--repo-root", "--format"}
    while i < len(args):
        token = args[i]
        if token.startswith("--"):
            if "=" in token:
                flag, value = token.split("=", 1)
            else:
                flag = token
                if flag not in known_flags:
                    print(f"usage error: unknown argument {flag}", file=sys.stderr)
                    return 2
                if i + 1 >= len(args):
                    print(f"usage error: {flag} requires a value", file=sys.stderr)
                    return 2
                value = args[i + 1]
                i += 1

            if flag == "--model":
                model = value
            elif flag == "--seed":
                try:
                    seed = int(value)
                except ValueError:
                    print("usage error: --seed must be an integer", file=sys.stderr)
                    return 2
            elif flag == "--retry-feedback":
                retry_feedback = value.split(",") if value else []
            elif flag == "--repo-root":
                repo_root = Path(value)
            elif flag == "--format":
                if value not in ("json", "text"):
                    print("usage error: invalid --format", file=sys.stderr)
                    return 2
                fmt = value
            else:
                print(f"usage error: unknown argument {flag}", file=sys.stderr)
                return 2
        else:
            positional.append(token)
        i += 1

    if not positional:
        print("usage error: missing <component-id>", file=sys.stderr)
        return 2
    component_id = positional[0]
    if len(positional) > 1:
        print("usage error: unknown argument", file=sys.stderr)
        return 2
    if model is None:
        print("usage error: --model is required", file=sys.stderr)
        return 2

    slug = _slug(component_id)
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_md.exists():
        print(f"usage error: unknown component {component_id}", file=sys.stderr)
        return 2

    result = run_component_gates(
        component_id,
        repo_root,
        model,
        seed=seed,
        llm_backend=None,
        retry_feedback=retry_feedback,
    )

    if fmt == "json":
        print(json.dumps(_to_jsonable(result), indent=2))
    else:
        _print_text(result)

    block_reason = _get(result, "block_reason")
    if block_reason == "model_call_error":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())