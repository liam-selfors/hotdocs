"""Component Gate Runner (comp-component-gate-runner).

Runs one component through its full per-component gauntlet: provenance
check, generation on a miss, verification dispatch, compliance scanning,
provenance write.
"""

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

_DEP_CACHE = {}


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    if component_id and component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError("could not locate tool root above component_gate_runner's own path")


def _resolve_dep_base(slug, repo_root):
    repo_root = Path(repo_root)
    candidate = repo_root / "gen" / slug
    if candidate.exists():
        return candidate
    return _tool_root() / "gen" / slug


def _load_dependency(module_name, slug, repo_root):
    base = _resolve_dep_base(slug, repo_root)
    flat = base / f"{module_name}.py"
    pkg_init = base / module_name / "__init__.py"
    if flat.is_file():
        path = flat
    elif pkg_init.is_file():
        path = pkg_init
    else:
        raise ImportError(f"cannot locate module {module_name!r} under {base}")

    cache_key = (module_name, str(path))
    cached = _DEP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _DEP_CACHE[cache_key] = module
    return module


def _unwrap_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _collect_gen_files(repo_root, slug):
    base = Path(repo_root) / "gen" / slug
    parts = []
    if base.exists():
        for path in sorted(base.rglob("*")):
            if path.is_dir():
                continue
            if "__pycache__" in path.parts:
                continue
            try:
                content = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            rel = path.relative_to(base)
            parts.append(f"--- {rel.as_posix()} ---\n{content}")
    return "\n".join(parts)


def _build_judge_prompt(criterion_text, requirement_text, interface_text, files_text):
    return (
        "You are judging whether a generated component satisfies an "
        "acceptance criterion.\n\n"
        f"Criterion:\n{criterion_text}\n\n"
        f"Requirement:\n{requirement_text}\n\n"
        f"Interface:\n{interface_text}\n\n"
        f"Generated files:\n{files_text}\n\n"
        'Respond with JSON exactly like {"result": "pass" | "fail", '
        '"rationale": "..."}.'
    )


def _judge(bundle, model, llm_backend, repo_root):
    try:
        endpoint = _load_dependency("llm_endpoint", "llm-endpoint", repo_root)
        criterion_text = _get(bundle, "criterion_text", "")
        requirement_text = _get(bundle, "requirement_text", "")
        interface_text = _get(bundle, "interface", "")
        component_id = _get(bundle, "component_id")
        slug = _slug(component_id) if component_id else ""
        files_text = _collect_gen_files(repo_root, slug)
        prompt = _build_judge_prompt(criterion_text, requirement_text, interface_text, files_text)
        response = endpoint.complete(prompt, model, backend=llm_backend)
    except Exception as exc:
        return {"result": "fail", "rationale": f"judge unavailable: {exc}"}

    model_call_error = _get(response, "model_call_error")
    if model_call_error:
        message = _get(model_call_error, "message", str(model_call_error))
        return {"result": "fail", "rationale": f"judge unavailable: {message}"}

    text = _get(response, "text")
    if not text:
        return {"result": "fail", "rationale": "judge unavailable: empty response"}

    try:
        unwrapped = _unwrap_code_fence(text)
        parsed = json.loads(unwrapped)
    except Exception as exc:
        return {"result": "fail", "rationale": f"judge unavailable: {exc}"}

    if not isinstance(parsed, dict):
        return {"result": "fail", "rationale": "judge unavailable: malformed response"}

    result = parsed.get("result")
    rationale = parsed.get("rationale")
    if result not in ("pass", "fail"):
        return {"result": "fail", "rationale": f"judge unavailable: invalid result {result!r}"}

    return {"result": result, "rationale": rationale}


def _run_sealed_gates(component_id, repo_root, sealed_key, judge, test_author):
    vo = _load_dependency("verifier_orchestrator", "verifier-orchestrator", repo_root)
    verification_report = vo.verify(component_id, repo_root, judge=judge, test_author=test_author)

    ls = _load_dependency("license_scanner", "license-scanner", repo_root)
    license_result = ls.scan(component_id, repo_root)

    ss = _load_dependency("secret_scanner", "secret-scanner", repo_root)
    secret_result = ss.scan(repo_root)

    pw = _load_dependency("provenance_writer", "provenance-writer", repo_root)
    sealed_inputs = {
        "component_id": component_id,
        "owners": _get(sealed_key, "owners"),
        "source_path": _get(sealed_key, "source_path"),
        "source_hash": _get(sealed_key, "source_hash"),
        "verifier_version": _get(sealed_key, "verifier_version"),
        "verification_report": verification_report,
    }
    pw.write_sealed_provenance(component_id, sealed_inputs, repo_root)

    overall = _get(verification_report, "overall")
    blocked = overall != "pass"
    block_reason = "verification_failed" if blocked else None

    return {
        "component_id": component_id,
        "provenance_hit": False,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": None,
        "verification": verification_report,
        "license_scan": license_result,
        "secret_scan": secret_result,
    }


def _run_generated_gates(component_id, repo_root, model, seed, llm_backend, retry_feedback, pc, judge, test_author):
    key = pc.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")

    check_result = pc.check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)
    hit = _get(check_result, "hit")
    if hit:
        hit_verification = _get(check_result, "verification_report")
        hit_license = _get(check_result, "license_scan")
        hit_secret = _get(check_result, "secret_scan")
        overall = _get(hit_verification, "overall") if hit_verification is not None else None
        license_blocked = _get(hit_license, "blocked") if hit_license is not None else None
        if overall == "pass" and license_blocked is not True:
            return {
                "component_id": component_id,
                "provenance_hit": True,
                "blocked": False,
                "block_reason": None,
                "model_call_error": None,
                "verification": hit_verification,
                "license_scan": hit_license,
                "secret_scan": hit_secret,
            }

    sba = _load_dependency("spec_bundle_assembler", "spec-bundle-assembler", repo_root)
    bundle = sba.assemble(component_id, repo_root=repo_root, mode="cold")

    gen = _load_dependency("generator", "generator", repo_root)
    generation_result = gen.generate(
        bundle, model, retry_feedback, repo_root=repo_root, llm_backend=llm_backend,
    )

    files = _get(generation_result, "files")
    verification_report = None
    if files:
        vo = _load_dependency("verifier_orchestrator", "verifier-orchestrator", repo_root)
        verification_report = vo.verify(component_id, repo_root, judge=judge, test_author=test_author)

    ls = _load_dependency("license_scanner", "license-scanner", repo_root)
    license_result = ls.scan(component_id, repo_root)

    ss = _load_dependency("secret_scanner", "secret-scanner", repo_root)
    secret_result = ss.scan(repo_root)

    try:
        pt = _load_dependency("provenance_tracker", "provenance-tracker", repo_root)
        pt.write_attempt_record(
            component_id, generation_result, verification_report, spec_bundle_hash, repo_root,
        )
    except Exception:
        pass

    if files:
        slug = _slug(component_id)
        attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
        attempts = len(list(attempts_dir.glob("*"))) if attempts_dir.exists() else 0

        pw = _load_dependency("provenance_writer", "provenance-writer", repo_root)
        provenance_inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": license_result,
            "secret_scan_result": secret_result,
            "provenance_hit": False,
            "attempts": attempts,
            "gate_versions": gate_versions,
        }
        pw.write_provenance(component_id, provenance_inputs, repo_root)

    model_call_error = _get(generation_result, "model_call_error")

    if files:
        overall = _get(verification_report, "overall")
        if overall == "pass":
            blocked = False
            block_reason = None
        else:
            blocked = True
            block_reason = "verification_failed"
    else:
        blocked = True
        block_reason = "model_call_error"

    return {
        "component_id": component_id,
        "provenance_hit": False,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": model_call_error if not files else None,
        "verification": verification_report,
        "license_scan": license_result,
        "secret_scan": secret_result,
    }


def run_component_gates(component_id, repo_root, model, seed=0, llm_backend=None, retry_feedback=None):
    repo_root = Path(repo_root)

    pc = _load_dependency("provenance_checker", "provenance-checker", repo_root)

    def judge(bundle):
        return _judge(bundle, model, llm_backend, repo_root)

    def test_author(bundle):
        ta = _load_dependency("test_author", "test-author", repo_root)
        return ta.author_test(bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend)

    sealed_key = pc.current_sealed_key(component_id, repo_root)

    if sealed_key is not None:
        return _run_sealed_gates(component_id, repo_root, sealed_key, judge, test_author)

    return _run_generated_gates(
        component_id, repo_root, model, seed, llm_backend, retry_feedback,
        pc, judge, test_author,
    )


def _to_jsonable(value):
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _to_jsonable(to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(dataclasses.asdict(value))
    try:
        return _to_jsonable(vars(value))
    except TypeError:
        return value


def _print_text(result):
    component_id = _get(result, "component_id")
    provenance_hit = _get(result, "provenance_hit")
    blocked = _get(result, "blocked")
    block_reason = _get(result, "block_reason")
    license_scan = _get(result, "license_scan")
    secret_scan = _get(result, "secret_scan")
    model_call_error = _get(result, "model_call_error")

    print(component_id)
    if provenance_hit:
        print("provenance hit")
    else:
        print(block_reason if blocked else "passed")

    if license_scan is not None:
        print(f"license_scan blocked: {_get(license_scan, 'blocked')}")
    if secret_scan is not None:
        print(f"secret_scan flagged: {_get(secret_scan, 'flagged')}")

    if model_call_error:
        category = _get(model_call_error, "category")
        message = _get(model_call_error, "message")
        print(f"model_call_error: {category}: {message}")

    if license_scan is not None and _get(license_scan, "evaluated") is False:
        reason = _get(license_scan, "reason")
        print(f"license_scan not evaluated: {reason}")


_KNOWN_FLAGS = {"--model", "--seed", "--retry-feedback", "--repo-root", "--format"}


def main(argv=None):
    argv = list(argv) if argv is not None else sys.argv[1:]

    if not argv or argv[0] != "generate":
        print("usage error: expected 'generate' as the first argument", file=sys.stderr)
        return 2

    rest = argv[1:]

    model = None
    seed = 0
    retry_feedback = None
    repo_root = Path.cwd()
    fmt = "text"
    positional = []

    i = 0
    while i < len(rest):
        token = rest[i]
        if token.startswith("--"):
            if "=" in token:
                flag, _, value = token.partition("=")
            else:
                flag = token
                value = None

            if flag not in _KNOWN_FLAGS:
                print(f"usage error: unknown argument {token}", file=sys.stderr)
                return 2

            if value is None:
                if i + 1 >= len(rest):
                    print(f"usage error: {flag} requires a value", file=sys.stderr)
                    return 2
                value = rest[i + 1]
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
                retry_feedback = value.split(",") if value != "" else []
            elif flag == "--repo-root":
                repo_root = Path(value)
            elif flag == "--format":
                if value not in ("json", "text"):
                    print("usage error: invalid --format", file=sys.stderr)
                    return 2
                fmt = value
        else:
            positional.append(token)
        i += 1

    if len(positional) != 1:
        print("usage error: expected exactly one component id", file=sys.stderr)
        return 2

    component_id = positional[0]

    if not component_id.startswith("comp-"):
        print(f"usage error: invalid component id {component_id}", file=sys.stderr)
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
        component_id, repo_root, model, seed=seed,
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