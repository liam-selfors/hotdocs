"""Generation loop: bounded generate / surface-check / verify attempts."""

import dataclasses
import hashlib
import importlib.util
import json
import sys
import uuid
from pathlib import Path

RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


def _get(obj, name):
    """Dual dict-or-attribute access; an absent field reads as None."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    return next(d.parent for d in Path(__file__).resolve().parents if d.name == "gen")


def _load(repo_root, slug, module):
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module}.py"
    name = f"_generation_loop_dep_{module}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


def _plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


@dataclasses.dataclass
class AttemptLoopResult:
    passed: bool
    stop_reason: str
    attempts: list
    generation_result: object = None
    verification_report: object = None
    surface_report: object = None

    def to_dict(self):
        return {
            "passed": self.passed,
            "stop_reason": self.stop_reason,
            "attempts": [dict(a) for a in self.attempts],
            "generation_result": _plain(self.generation_result),
            "verification_report": _plain(self.verification_report),
            "surface_report": _plain(self.surface_report),
        }


def _unfence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped


def make_closures(model, seed, repo_root, llm_backend=None):
    repo_root = Path(repo_root)
    loaded = {}

    def _dep(slug, module):
        if slug not in loaded:
            loaded[slug] = _load(repo_root, slug, module)
        return loaded[slug]

    def test_author(bundle):
        mod = _dep("test-author", "test_author")
        return mod.author_test(bundle, model, seed=seed, repo_root=repo_root,
                               llm_backend=llm_backend)

    def judge(bundle):
        component_id = bundle["component_id"]
        slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
        code_dir = repo_root / "gen" / slug
        file_parts = []
        for path in sorted(code_dir.rglob("*")):
            if path.is_file() and "__pycache__" not in path.relative_to(code_dir).parts:
                rel = path.relative_to(code_dir).as_posix()
                content = path.read_text(encoding="utf-8", errors="replace")
                file_parts.append(f"### File: {rel}\n\n{content}")
        prompt = (
            "You are judging whether a component's implementation satisfies one "
            "acceptance criterion.\n\n"
            "## Criterion\n\n" + str(bundle["criterion_text"]) + "\n\n"
            "## Requirement\n\n" + str(bundle["requirement_text"]) + "\n\n"
            "## Interface\n\n" + str(bundle["interface"]) + "\n\n"
            "## Implementation files\n\n" + "\n\n".join(file_parts) + "\n\n"
            "Reply with JSON only, exactly of the form "
            '{"result": "pass" | "fail", "rationale": "..."}.\n'
        )
        mod = _dep("llm-endpoint", "llm_endpoint")
        response = mod.complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return {"result": "fail",
                    "rationale": f"judge unavailable: model call error ({_get(error, 'category')})"}
        text = _get(response, "text") or ""
        try:
            data = json.loads(_unfence(text))
        except ValueError:
            return {"result": "fail", "rationale": "judge unavailable: unparseable reply"}
        if not isinstance(data, dict) or data.get("result") not in ("pass", "fail"):
            return {"result": "fail", "rationale": "judge unavailable: invalid result"}
        return {"result": data["result"], "rationale": data.get("rationale")}

    return (test_author, judge)


def _test_file(repo_root, slug, criterion_id):
    name = "test_" + str(criterion_id).lower().replace("-", "_") + ".py"
    return Path(repo_root) / "verification" / slug / "generated-test" / name


def run_attempts(component_id, bundle, repo_root, model, *, mode="single",
                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    if mode not in ("single", "agentic") or max_attempts < 1:
        raise ValueError("invalid mode or max_attempts")

    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    deps = {}

    def dep(dep_slug, module):
        if dep_slug not in deps:
            deps[dep_slug] = _load(repo_root, dep_slug, module)
        return deps[dep_slug]

    test_author, judge = make_closures(model, seed, repo_root, llm_backend)

    feedback = sorted(set(retry_feedback or []))
    attempts = []
    passed = False
    stop_reason = None
    gen_result = None
    ver_report = None
    surf_report = None
    prev_hashes = {}
    reauthored_done = set()

    for number in range(1, max_attempts + 1):
        fb_arg = list(feedback) if feedback else None
        if mode == "single":
            gen_result = dep("generator", "generator").generate(
                bundle, model, fb_arg, repo_root=repo_root, llm_backend=llm_backend)
        else:
            gen_result = dep("agentic-generator", "agentic_generator").generate_agentic(
                bundle, model, fb_arg, repo_root=repo_root,
                allow_unisolated_exec=allow_unisolated_exec)
        ver_report = None
        surf_report = None
        cur_hashes = {}
        stop = None
        entry = {
            "number": number,
            "outcome": None,
            "retry_feedback": list(feedback),
            "error_category": None,
            "surface_ok": None,
            "overall": None,
            "failed_requirements": [],
            "transcript_sha256": _get(gen_result, "transcript_sha256"),
            "reauthored_tests": [],
        }
        files = _get(gen_result, "files") or {}

        if _get(gen_result, "refused"):
            entry["outcome"] = "refused"
            stop = "refused"
        elif not files:
            entry["outcome"] = "generation_failed"
            category = _get(_get(gen_result, "model_call_error"), "category")
            entry["error_category"] = category
            if category == "environment":
                stop = "environment"
            elif category not in RETRIED_CATEGORIES:
                stop = "not_retried"
        else:
            surf_report = dep("surface-checker", "surface_checker").check_surface(
                component_id, repo_root)
            if not _get(surf_report, "ok"):
                entry["outcome"] = "surface_failed"
                entry["surface_ok"] = False
            else:
                entry["surface_ok"] = True
                ver_report = dep("verifier-orchestrator", "verifier_orchestrator").verify(
                    component_id, repo_root, judge=judge, test_author=test_author)
                overall = _get(ver_report, "overall")
                entry["overall"] = overall
                criteria = _get(ver_report, "criteria") or []
                if overall == "pass":
                    entry["outcome"] = "passed"
                    passed = True
                    stop = "passed"
                    if mode == "single":
                        dep("generator", "generator").commit_cache(gen_result, repo_root=repo_root)
                else:
                    entry["outcome"] = "verification_failed"
                    entry["failed_requirements"] = sorted({
                        _get(c, "covers") for c in criteria
                        if _get(c, "result") == "fail"
                        and _get(c, "failure_origin") not in ("test", "environment")
                    })
                    if any(_get(c, "failure_origin") == "environment" for c in criteria):
                        stop = "environment"
                    for c in criteria:
                        if (_get(c, "kind") == "generated-test" and _get(c, "result") == "fail"
                                and _get(c, "failure_origin") == "implementation"):
                            path = _test_file(repo_root, slug, _get(c, "id"))
                            if path.is_file():
                                cur_hashes[_get(c, "id")] = hashlib.sha256(
                                    path.read_bytes()).hexdigest()

        if stop is None and number == max_attempts:
            stop = "max_attempts"

        if stop is None:
            repeated = sorted(
                cid for cid, digest in cur_hashes.items()
                if prev_hashes.get(cid) == digest and cid not in reauthored_done
            )
            for cid in repeated:
                _test_file(repo_root, slug, cid).unlink()
                reauthored_done.add(cid)
            entry["reauthored_tests"] = repeated
        prev_hashes = cur_hashes

        feedback = sorted(set(feedback) | set(entry["failed_requirements"]))
        attempts.append(entry)
        if on_attempt is not None:
            on_attempt(entry, gen_result, ver_report)
        if stop is not None:
            stop_reason = stop
            break

    return AttemptLoopResult(
        passed=passed,
        stop_reason=stop_reason,
        attempts=attempts,
        generation_result=gen_result,
        verification_report=ver_report,
        surface_report=surf_report,
    )
