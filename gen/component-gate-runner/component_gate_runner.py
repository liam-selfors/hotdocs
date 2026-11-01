"""hotdocs component-gate-runner: per-component generation/verification gauntlet."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path


def _get(obj, key, default=None):
    """Dual dict-or-attribute access, since any dependency result may be either shape."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _load_dependency(repo_root, dep_slug, module_name):
    base = Path(repo_root) / "gen" / dep_slug
    flat_path = base / f"{module_name}.py"
    pkg_path = base / module_name / "__init__.py"
    if flat_path.is_file():
        path = flat_path
    elif pkg_path.is_file():
        path = pkg_path
    else:
        raise ImportError(f"dependency module {module_name!r} not found under {base}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _is_sealed(component_id, repo_root):
    slug = _slug(component_id)
    path = Path(repo_root) / "specs" / "components" / slug / "component.md"
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    end = text.find("---", 3)
    if end == -1:
        return False
    frontmatter = text[3:end]
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("sealed:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            return value.lower() == "true"
    return False


def _unwrap_fence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _collect_gen_files(repo_root, slug):
    base = Path(repo_root) / "gen" / slug
    files = {}
    if not base.exists():
        return files
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(base))
        try:
            files[rel] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            files[rel] = ""
    return files


def _build_judge_prompt(repo_root, bundle):
    criterion_text = _get(bundle, "criterion_text", "")
    requirement_text = _get(bundle, "requirement_text", "")
    interface_text = _get(bundle, "interface", "")
    bundle_component_id = _get(bundle, "component_id", "")
    slug = _slug(bundle_component_id) if bundle_component_id else ""
    files = _collect_gen_files(repo_root, slug) if slug else {}
    files_section = "\n\n".join(
        f"--- {path} ---\n{content}" for path, content in files.items()
    )
    return (
        "Criterion:\n" + criterion_text + "\n\n"
        "Requirement:\n" + requirement_text + "\n\n"
        "Interface:\n" + interface_text + "\n\n"
        "Files:\n" + files_section + "\n\n"
        'Respond with JSON of exactly this shape: '
        '{"result": "pass" | "fail", "rationale": "..."}'
    )


def _json_default(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if hasattr(obj, "__dict__"):
        return vars(obj)
    return str(obj)


def run_component_gates(
    component_id,
    repo_root,
    model,
    seed=0,
    llm_backend=None,
    retry_feedback=None,
):
    repo_root = Path(repo_root)
    modules = {}

    def load(dep_slug, module_name):
        if module_name not in modules:
            modules[module_name] = _load_dependency(repo_root, dep_slug, module_name)
        return modules[module_name]

    def test_author_closure(bundle):
        mod = load("test-author", "test_author")
        return mod.author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    def judge_closure(bundle):
        try:
            llm_endpoint_mod = load("llm-endpoint", "llm_endpoint")
            prompt = _build_judge_prompt(repo_root, bundle)
            response = llm_endpoint_mod.complete(prompt, model, backend=llm_backend)
        except Exception as exc:  # noqa: BLE001 - judge must never raise
            return {"result": "fail", "rationale": f"judge unavailable: {exc}"}

        error = _get(response, "model_call_error")
        if error:
            msg = _get(error, "message", str(error))
            return {"result": "fail", "rationale": f"judge unavailable: {msg}"}

        text = _get(response, "text")
        if not text:
            return {"result": "fail", "rationale": "judge unavailable: empty response"}

        try:
            unwrapped = _unwrap_fence(text)
            parsed = json.loads(unwrapped)
        except Exception as exc:  # noqa: BLE001
            return {"result": "fail", "rationale": f"judge unavailable: {exc}"}

        result = _get(parsed, "result")
        rationale = _get(parsed, "rationale")
        if result not in ("pass", "fail"):
            return {
                "result": "fail",
                "rationale": f"judge unavailable: invalid result {result!r}",
            }
        return {"result": result, "rationale": rationale}

    if _is_sealed(component_id, repo_root):
        verifier_mod = load("verifier-orchestrator", "verifier_orchestrator")
        verification_report = verifier_mod.verify(
            component_id, repo_root, judge=judge_closure, test_author=test_author_closure
        )
        license_mod = load("license-scanner", "license_scanner")
        license_scan_result = license_mod.scan(component_id, repo_root)
        secret_mod = load("secret-scanner", "secret_scanner")
        secret_scan_result = secret_mod.scan(repo_root)

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
            "license_scan": license_scan_result,
            "secret_scan": secret_scan_result,
        }

    provenance_checker_mod = load("provenance-checker", "provenance_checker")
    key = provenance_checker_mod.current_provenance_key(component_id, repo_root)
    spec_bundle_hash = _get(key, "spec_bundle_hash")
    gate_versions = _get(key, "gate_versions")
    check_result = provenance_checker_mod.check_provenance(
        component_id, spec_bundle_hash, gate_versions, repo_root
    )

    hit = _get(check_result, "hit")
    if hit:
        hit_verification = _get(check_result, "verification_report")
        hit_license_scan = _get(check_result, "license_scan")
        hit_secret_scan = _get(check_result, "secret_scan")
        overall = _get(hit_verification, "overall")
        lic_blocked = _get(hit_license_scan, "blocked")
        if overall == "pass" and lic_blocked is not True:
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

    assembler_mod = load("spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler_mod.assemble(component_id, repo_root=repo_root, mode="cold")

    generator_mod = load("generator", "generator")
    generation_result = generator_mod.generate(
        bundle, model, retry_feedback, repo_root=repo_root, llm_backend=llm_backend
    )

    files = _get(generation_result, "files") or {}
    if files:
        verifier_mod = load("verifier-orchestrator", "verifier_orchestrator")
        verification_report = verifier_mod.verify(
            component_id, repo_root, judge=judge_closure, test_author=test_author_closure
        )
    else:
        verification_report = None

    license_mod = load("license-scanner", "license_scanner")
    license_scan_result = license_mod.scan(component_id, repo_root)
    secret_mod = load("secret-scanner", "secret_scanner")
    secret_scan_result = secret_mod.scan(repo_root)

    try:
        tracker_mod = load("provenance-tracker", "provenance_tracker")
        tracker_mod.write_attempt_record(
            component_id, generation_result, verification_report, spec_bundle_hash, repo_root
        )
    except Exception:  # noqa: BLE001 - must never change this component's result
        pass

    model_call_error = _get(generation_result, "model_call_error")
    if not files:
        blocked = True
        block_reason = "model_call_error"
        out_model_call_error = model_call_error
        out_verification = None
    else:
        overall = _get(verification_report, "overall")
        if overall == "pass":
            blocked = False
            block_reason = None
        else:
            blocked = True
            block_reason = "verification_failed"
        out_model_call_error = None
        out_verification = verification_report

    if files:
        slug = _slug(component_id)
        attempts_dir = repo_root / ".hotdocs" / "attempts" / slug
        attempts = 0
        if attempts_dir.exists():
            attempts = len([p for p in attempts_dir.iterdir() if p.is_file()])
        inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": license_scan_result,
            "secret_scan_result": secret_scan_result,
            "provenance_hit": False,
            "attempts": attempts,
            "gate_versions": gate_versions,
        }
        writer_mod = load("provenance-writer", "provenance_writer")
        writer_mod.write_provenance(component_id, inputs, repo_root)

    return {
        "component_id": component_id,
        "provenance_hit": False,
        "blocked": blocked,
        "block_reason": block_reason,
        "model_call_error": out_model_call_error,
        "verification": out_verification,
        "license_scan": license_scan_result,
        "secret_scan": secret_scan_result,
    }


def _parse_flags(tokens):
    flags = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("--"):
            raise ValueError(f"unknown argument: {tok}")
        if "=" in tok:
            key, value = tok[2:].split("=", 1)
            flags[key] = value
            i += 1
        else:
            key = tok[2:]
            if i + 1 >= len(tokens):
                raise ValueError(f"flag --{key} given last with no value")
            flags[key] = tokens[i + 1]
            i += 2
    return flags


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)

    if not args or args[0] != "generate":
        return 2

    args = args[1:]
    if not args or args[0].startswith("--"):
        return 2

    component_id = args[0]
    rest = args[1:]

    known_flags = {"model", "seed", "retry-feedback", "repo-root", "format"}
    try:
        flags = _parse_flags(rest)
    except ValueError:
        return 2

    for key in flags:
        if key not in known_flags:
            return 2

    if "model" not in flags:
        return 2
    model = flags["model"]

    try:
        seed = int(flags.get("seed", "0"))
    except ValueError:
        return 2

    retry_feedback = None
    if "retry-feedback" in flags:
        retry_feedback = [part for part in flags["retry-feedback"].split(",") if part]

    repo_root = Path(flags.get("repo-root", "."))

    fmt = flags.get("format", "text")
    if fmt not in ("json", "text"):
        return 2

    slug = _slug(component_id)
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_md.exists():
        return 2

    result = run_component_gates(
        component_id, repo_root, model, seed=seed, retry_feedback=retry_feedback
    )

    if fmt == "json":
        print(json.dumps(result, default=_json_default))
    else:
        if result.get("provenance_hit"):
            status = "provenance hit"
        else:
            status = result.get("block_reason") or "passed"
        print(f"{component_id}: {status}")
        license_scan = result.get("license_scan")
        secret_scan = result.get("secret_scan")
        print(f"license_scan: blocked={_get(license_scan, 'blocked')}")
        print(f"secret_scan: flagged={_get(secret_scan, 'flagged')}")

    if result.get("block_reason") == "model_call_error":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))