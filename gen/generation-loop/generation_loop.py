"""Generation loop: bounded generate / surface-check / verify attempts."""

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from pathlib import Path

RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


@dataclasses.dataclass
class AttemptLoopResult:
    passed: bool
    stop_reason: str
    attempts: list
    generation_result: object
    verification_report: object
    surface_report: object

    def to_dict(self):
        return dataclasses.asdict(self)


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load(slug, repo_root):
    module = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    name = f"_generation_loop_dep_{module}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, directory / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


def _loader(repo_root):
    cache = {}

    def dep(slug):
        if slug not in cache:
            cache[slug] = _load(slug, repo_root)
        return cache[slug]

    return dep


def _unwrap_fence(text):
    m = re.match(r"^```[^\n]*\n(.*?)\n?```\s*$", text, re.S)
    if m:
        return m.group(1)
    return text


def make_closures(model, seed, repo_root, llm_backend=None):
    dep = _loader(repo_root)

    def test_author(bundle):
        return dep("test-author").author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend)

    def judge(bundle):
        slug = bundle["component_id"][len("comp-"):] if bundle["component_id"].startswith("comp-") \
            else bundle["component_id"]
        code_dir = Path(repo_root) / "gen" / slug
        parts = []
        for path in sorted(code_dir.rglob("*")):
            if "__pycache__" in path.relative_to(code_dir).parts or not path.is_file():
                continue
            rel = path.relative_to(code_dir).as_posix()
            parts.append(f"### File: {rel}\n{path.read_text(encoding='utf-8', errors='replace')}")
        prompt = (
            "You are judging whether a component's code satisfies one acceptance criterion.\n\n"
            f"## Criterion\n{bundle['criterion_text']}\n\n"
            f"## Requirement\n{bundle['requirement_text']}\n\n"
            f"## Interface\n{bundle['interface']}\n\n"
            "## Code\n" + "\n\n".join(parts) + "\n\n"
            'Reply with JSON only: {"result": "pass" | "fail", "rationale": "..."}\n'
        )
        response = dep("llm-endpoint").complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return {"result": "fail",
                    "rationale": f"judge unavailable: model call error: {_get(error, 'category')}"}
        text = _unwrap_fence((_get(response, "text") or "").strip())
        try:
            parsed = json.loads(text)
        except ValueError:
            return {"result": "fail", "rationale": "judge unavailable: unparseable reply"}
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if result not in ("pass", "fail"):
            return {"result": "fail",
                    "rationale": f"judge unavailable: invalid result {result!r}"}
        return {"result": result, "rationale": parsed.get("rationale")}

    return (test_author, judge)


def _test_path(repo_root, slug, criterion_id):
    name = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    return Path(repo_root) / "verification" / slug / "generated-test" / name


def _impl_failures(report, repo_root, slug):
    found = {}
    for c in _get(report, "criteria") or []:
        if (_get(c, "kind") == "generated-test" and _get(c, "result") == "fail"
                and _get(c, "failure_origin") == "implementation"):
            path = _test_path(repo_root, slug, _get(c, "id"))
            if path.is_file():
                found[_get(c, "id")] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def run_attempts(component_id, bundle, repo_root, model, *, mode="single", max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    if mode not in ("single", "agentic") or max_attempts < 1:
        raise ValueError("invalid mode or max_attempts")
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    dep = _loader(repo_root)
    test_author, judge = make_closures(model, seed, repo_root, llm_backend)

    feedback = sorted(set(retry_feedback or []))
    attempts = []
    passed = False
    stop_reason = "max_attempts"
    generation_result = None
    verification_report = None
    surface_report = None
    prev_impl = None
    reauthored = set()

    for number in range(1, max_attempts + 1):
        fb_arg = list(feedback) or None
        if mode == "single":
            result = dep("generator").generate(
                bundle, model, fb_arg, repo_root=repo_root, llm_backend=llm_backend)
        else:
            result = dep("agentic-generator").generate_agentic(
                bundle, model, fb_arg, repo_root=repo_root,
                allow_unisolated_exec=allow_unisolated_exec)
        generation_result = result
        surface_report = None
        verification_report = None
        entry = {"number": number, "outcome": None, "retry_feedback": list(feedback),
                 "error_category": None, "surface_ok": None, "overall": None,
                 "failed_requirements": [],
                 "transcript_sha256": _get(result, "transcript_sha256"),
                 "reauthored_tests": []}
        stop = None
        impl = None

        if _get(result, "refused"):
            entry["outcome"] = "refused"
            stop = "refused"
        elif _get(result, "files"):
            surface_report = dep("surface-checker").check_surface(component_id, repo_root)
            if not _get(surface_report, "ok"):
                entry["outcome"] = "surface_failed"
                entry["surface_ok"] = False
            else:
                entry["surface_ok"] = True
                verification_report = dep("verifier-orchestrator").verify(
                    component_id, repo_root, judge=judge, test_author=test_author)
                overall = _get(verification_report, "overall")
                entry["overall"] = overall
                criteria = _get(verification_report, "criteria") or []
                entry["failed_requirements"] = sorted({
                    _get(c, "covers") for c in criteria
                    if _get(c, "result") == "fail"
                    and _get(c, "failure_origin") not in ("test", "environment")})
                impl = _impl_failures(verification_report, repo_root, slug)
                if overall == "pass":
                    entry["outcome"] = "passed"
                    stop = "passed"
                else:
                    entry["outcome"] = "verification_failed"
                    if any(_get(c, "failure_origin") == "environment" for c in criteria):
                        stop = "environment"
                    elif number < max_attempts and prev_impl is not None:
                        deleted = sorted(
                            cid for cid, sha in impl.items()
                            if prev_impl.get(cid) == sha and cid not in reauthored)
                        for cid in deleted:
                            _test_path(repo_root, slug, cid).unlink()
                            reauthored.add(cid)
                        entry["reauthored_tests"] = deleted
        else:
            entry["outcome"] = "generation_failed"
            category = _get(_get(result, "model_call_error"), "category")
            entry["error_category"] = category
            if category == "environment":
                stop = "environment"
            elif category not in RETRIED_CATEGORIES:
                stop = "not_retried"

        prev_impl = impl
        attempts.append(entry)
        feedback = sorted(set(feedback) | set(entry["failed_requirements"]))

        if on_attempt is not None:
            on_attempt(entry, result, verification_report)

        if stop == "passed":
            passed = True
            if mode == "single":
                dep("generator").commit_cache(result, repo_root=repo_root)
        if stop is not None:
            stop_reason = stop
            break

    return AttemptLoopResult(passed=passed, stop_reason=stop_reason, attempts=attempts,
                             generation_result=generation_result,
                             verification_report=verification_report,
                             surface_report=surface_report)
