"""hotdocs generate: the per-component gauntlet (R-GATE-001..010)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _load_module(repo_root, slug):
    repo_root = Path(repo_root)
    module_basename = slug.replace("-", "_")
    base = repo_root / "gen" / slug
    pkg_init = base / module_basename / "__init__.py"
    flat = base / f"{module_basename}.py"

    if pkg_init.exists():
        path = pkg_init
        search_locations = [str(path.parent)]
    elif flat.exists():
        path = flat
        search_locations = None
    else:
        raise ImportError(f"no module found for {slug!r} under {base}")

    key = hashlib.sha256(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:16]
    unique_name = f"_hotdocs_dep_{module_basename}_{key}"

    if unique_name in sys.modules:
        return sys.modules[unique_name]

    spec = importlib.util.spec_from_file_location(
        unique_name, path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def _unwrap_code_fence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _judge(repo_root, bundle, model, llm_backend):
    repo_root = Path(repo_root)
    criterion_text = _get(bundle, "criterion_text", "")
    requirement_text = _get(bundle, "requirement_text", "")
    interface_text = _get(bundle, "interface", "")
    component_id = _get(bundle, "component_id", "")
    slug = _slug(component_id)

    gen_dir = repo_root / "gen" / slug
    file_sections = []
    if gen_dir.exists():
        for path in sorted(gen_dir.rglob("*")):
            if "__pycache__" in path.parts:
                continue
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(gen_dir)
            file_sections.append(f"--- {rel.as_posix()} ---\n{content}")

    files_text = "\n\n".join(file_sections)

    prompt = (
        "You are judging whether generated code satisfies an acceptance "
        "criterion.\n\n"
        f"Criterion:\n{criterion_text}\n\n"
        f"Requirement:\n{requirement_text}\n\n"
        f"Interface:\n{interface_text}\n\n"
        f"Generated files under gen/{slug}/:\n{files_text}\n\n"
        'Respond with JSON only: {"result": "pass" | "fail", "rationale": "..."}'
    )

    try:
        llm_endpoint = _load_module(repo_root, "llm-endpoint")
        response = llm_endpoint.complete(prompt, model, backend=llm_backend)
    except Exception as exc:
        return {"result": "fail", "rationale": f"judge unavailable: {exc}"}

    model_call_error = _get(response, "model_call_error")
    if model_call_error:
        reason = _get(model_call_error, "message", str(model_call_error))
        return {"result": "fail", "rationale": f"judge unavailable: {reason}"}

    text = _get(response, "text")
    if not text:
        return {"result": "fail", "rationale": "judge unavailable: empty response"}

    unwrapped = _unwrap_code_fence(text)

    try:
        parsed = json.loads(unwrapped)
    except (json.JSONDecodeError, TypeError) as exc:
        return {
            "result": "fail",
            "rationale": f"judge unavailable: unparseable response: {exc}",
        }

    if not isinstance(parsed, dict):
        return {
            "result": "fail",
            "rationale": "judge unavailable: response not a JSON object",
        }

    result = parsed.get("result")
    rationale = parsed.get("rationale")
    if result not in ("pass", "fail"):
        return {
            "result": "fail",
            "rationale": f"judge unavailable: invalid result {result!r}",
        }

    return {"result": result, "rationale": rationale}


def _run_sealed(component_id, repo_root, sealed_key, judge_closure, test_author_closure):
    verifier_orchestrator = _load_module(repo_root, "verifier-orchestrator")
    verification_report = verifier_orchestrator.verify(
        component_id, repo_root, judge=judge_closure, test_author=test_author_closure
    )

    license_scanner = _load_module(repo_root, "license-scanner")
    license_scan = license_scanner.scan(component_id, repo_root)

    secret_scanner = _load_module(repo_root, "secret-scanner")
    secret_scan = secret_scanner.scan(repo_root)

    provenance_writer = _load_module(repo_root, "provenance-writer")
    inputs = {
        "component_id": component_id,
        "owners": _get(sealed_key, "owners"),
        "source_path": _get(sealed_key, "source_path"),
        "source_hash": _get(sealed_key, "source_hash"),
        "verifier_version": _get(sealed_key, "verifier_version"),
        "verification_report": verification_report,
    }
    provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)

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
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _run_generated(
    component_id, repo_root, model, seed, llm_backend, retry_feedback,
    judge_closure, test_author_closure,
):
    provenance_checker = _load_module(repo_root, "provenance-checker")
    key = provenance_checker.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")

    check_result = provenance_checker.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root
    )
    hit = _get(check_result, "hit")

    if hit:
        verification_report_hit = _get(check_result, "verification_report")
        license_scan_hit = _get(check_result, "license_scan")
        overall = _get(verification_report_hit, "overall")
        license_blocked = _get(license_scan_hit, "blocked")
        if overall == "pass" and license_blocked is not True:
            return {
                "component_id": component_id,
                "provenance_hit": True,
                "blocked": False,
                "block_reason": None,
                "model_call_error": None,
                "verification": verification_report_hit,
                "license_scan": license_scan_hit,
                "secret_scan": _get(check_result, "secret_scan"),
            }

    spec_bundle_assembler = _load_module(repo_root, "spec-bundle-assembler")
    bundle = spec_bundle_assembler.assemble(component_id, repo_root=repo_root, mode="cold")

    generator = _load_module(repo_root, "generator")
    generation_result = generator.generate(
        bundle, model, retry_feedback, repo_root=repo_root, llm_backend=llm_backend
    )

    files = _get(generation_result, "files")
    verification_report = None

    if files:
        verifier_orchestrator = _load_module(repo_root, "verifier-orchestrator")
        verification_report = verifier_orchestrator.verify(
            component_id, repo_root, judge=judge_closure, test_author=test_author_closure
        )

    license_scanner = _load_module(repo_root, "license-scanner")
    license_scan = license_scanner.scan(component_id, repo_root)

    secret_scanner = _load_module(repo_root, "secret-scanner")
    secret_scan = secret_scanner.scan(repo_root)

    try:
        provenance_tracker = _load_module(repo_root, "provenance-tracker")
        provenance_tracker.write_attempt_record(
            component_id, generation_result, verification_report, spec_bundle_hash, repo_root
        )
    except Exception:
        pass

    if not files:
        blocked = True
        block_reason = "model_call_error"
        result_model_call_error = _get(generation_result, "model_call_error")
        result_verification = None
    else:
        result_model_call_error = None
        overall = _get(verification_report, "overall")
        if overall == "pass":
            blocked = False
            block_reason = None
        else:
            blocked = True
            block_reason = "verification_failed"
        result_verification = verification_report

    if files:
        provenance_writer = _load_module(repo_root, "provenance-writer")
        attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / _slug(component_id)
        attempts = 0
        if attempts_dir.exists():
            attempts = len([p for p in attempts_dir.iterdir() if p.is_file()])
        inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": license_scan,
            "secret_scan_result": secret_scan,
            "provenance_hit": False,
            "attempts": attempts,
            "gate_versions": gate_versions,
        }
        provenance_writer.write_provenance(component_id, inputs, repo_root)

    return {
        "component_id": component_id,
        "provenance_hit": False,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": result_model_call_error,
        "verification": result_verification,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def run_component_gates(
    component_id, repo_root, model, seed=0, llm_backend=None, retry_feedback=None
):
    repo_root = Path(repo_root)

    def test_author_closure(bundle):
        test_author = _load_module(repo_root, "test-author")
        return test_author.author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    def judge_closure(bundle):
        return _judge(repo_root, bundle, model, llm_backend)

    provenance_checker = _load_module(repo_root, "provenance-checker")
    sealed_key = provenance_checker.current_sealed_key(component_id, repo_root)

    if sealed_key is not None:
        return _run_sealed(component_id, repo_root, sealed_key, judge_closure, test_author_closure)

    return _run_generated(
        component_id, repo_root, model, seed, llm_backend, retry_feedback,
        judge_closure, test_author_closure,
    )


def _json_default(obj):
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)

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
                flag, value = token.split("=", 1)
            else:
                flag = token
                i += 1
                if i >= len(rest):
                    print(f"usage error: {flag} requires a value", file=sys.stderr)
                    return 2
                value = rest[i]

            if flag == "--model":
                model = value
            elif flag == "--seed":
                try:
                    seed = int(value)
                except ValueError:
                    print("usage error: --seed must be an integer", file=sys.stderr)
                    return 2
            elif flag == "--retry-feedback":
                retry_feedback = [x for x in value.split(",") if x]
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

    if len(positional) < 1:
        print("usage error: missing <component-id>", file=sys.stderr)
        return 2
    if len(positional) > 1:
        print(f"usage error: unexpected argument {positional[1]!r}", file=sys.stderr)
        return 2

    component_id = positional[0]

    if model is None:
        print("usage error: --model is required", file=sys.stderr)
        return 2

    component_md = repo_root / "specs" / "components" / _slug(component_id) / "component.md"
    if not component_md.exists():
        print(f"usage error: unknown component {component_id!r}", file=sys.stderr)
        return 2

    result = run_component_gates(
        component_id, repo_root, model, seed=seed, retry_feedback=retry_feedback
    )

    if fmt == "json":
        print(json.dumps(result, default=_json_default))
    else:
        print(result.get("component_id"))
        if result.get("provenance_hit"):
            print("provenance hit")
        else:
            block_reason = result.get("block_reason")
            print(block_reason if block_reason else "passed")
        license_scan = result.get("license_scan")
        secret_scan = result.get("secret_scan")
        print(f"license_scan blocked: {_get(license_scan, 'blocked')}")
        print(f"secret_scan flagged: {_get(secret_scan, 'flagged')}")

    if result.get("block_reason") == "model_call_error":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())