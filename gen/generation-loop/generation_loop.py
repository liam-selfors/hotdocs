"""Generation loop: bounded generate / surface-check / verify attempts."""

import dataclasses
import hashlib
import importlib.util
import json
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


def _get(obj, name, default=None):
    if isinstance(obj, Mapping):
        value = obj.get(name)
    else:
        value = getattr(obj, name, None)
    return default if value is None else value


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_dependency(slug, repo_root):
    module = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module}.py"
    name = f"_generation_loop_dep_{module}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


class _Deps:
    def __init__(self, repo_root):
        self._repo_root = repo_root
        self._loaded = {}

    def get(self, slug):
        if slug not in self._loaded:
            self._loaded[slug] = _load_dependency(slug, self._repo_root)
        return self._loaded[slug]


def _jsonable(obj):
    if obj is None:
        return None
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


@dataclass
class AttemptLoopResult:
    passed: bool
    stop_reason: str
    attempts: list = field(default_factory=list)
    generation_result: object = None
    verification_report: object = None
    surface_report: object = None

    def to_dict(self):
        return {
            "passed": self.passed,
            "stop_reason": self.stop_reason,
            "attempts": [dict(a) for a in self.attempts],
            "generation_result": _jsonable(self.generation_result),
            "verification_report": _jsonable(self.verification_report),
            "surface_report": _jsonable(self.surface_report),
        }


def _unwrap_fence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def make_closures(model, seed, repo_root, llm_backend=None):
    deps = _Deps(repo_root)

    def test_author(bundle):
        mod = deps.get("test-author")
        return mod.author_test(bundle, model, seed=seed, repo_root=repo_root,
                               llm_backend=llm_backend)

    def judge(bundle):
        component_id = bundle["component_id"]
        slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
        code_dir = Path(repo_root) / "gen" / slug
        file_sections = []
        if code_dir.is_dir():
            for path in sorted(code_dir.rglob("*")):
                rel = path.relative_to(code_dir)
                if "__pycache__" in rel.parts or not path.is_file():
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
                file_sections.append(f"### File: {rel.as_posix()}\n\n{content}")
        prompt = (
            "You are judging whether a component's code satisfies one acceptance "
            "criterion.\n\n"
            "## Criterion\n\n" + str(bundle["criterion_text"]) + "\n\n"
            "## Requirement\n\n" + str(bundle["requirement_text"]) + "\n\n"
            "## Interface\n\n" + str(bundle["interface"]) + "\n\n"
            "## Code\n\n" + "\n\n".join(file_sections) + "\n\n"
            "Reply with JSON only: "
            '{"result": "pass" | "fail", "rationale": "..."}\n'
        )
        mod = deps.get("llm-endpoint")
        response = mod.complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return {"result": "fail",
                    "rationale": f"judge unavailable: model call error "
                                 f"{_get(error, 'category')}"}
        text = _unwrap_fence(_get(response, "text", ""))
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
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


def _implementation_failure_hashes(report, repo_root, slug):
    hashes = {}
    for criterion in _get(report, "criteria", []):
        if (_get(criterion, "kind") == "generated-test"
                and _get(criterion, "result") == "fail"
                and _get(criterion, "failure_origin") == "implementation"):
            cid = _get(criterion, "id")
            path = _test_path(repo_root, slug, cid)
            if path.is_file():
                hashes[cid] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def run_attempts(component_id, bundle, repo_root, model, *, mode="single",
                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    if mode not in ("single", "agentic"):
        raise ValueError(f"unknown mode: {mode!r}")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    deps = _Deps(repo_root)
    test_author, judge = make_closures(model, seed, repo_root, llm_backend)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id

    feedback = sorted(set(retry_feedback or []))
    attempts = []
    generation_result = None
    verification_report = None
    surface_report = None
    passed = False
    stop_reason = None
    prev_hashes = {}
    reauthored_once = set()

    for number in range(1, max_attempts + 1):
        feedback_arg = list(feedback) or None
        if mode == "single":
            generation_result = deps.get("generator").generate(
                bundle, model, feedback_arg, repo_root=repo_root, llm_backend=llm_backend)
        else:
            generation_result = deps.get("agentic-generator").generate_agentic(
                bundle, model, feedback_arg, repo_root=repo_root,
                allow_unisolated_exec=allow_unisolated_exec)
        surface_report = None
        verification_report = None

        entry = {
            "number": number,
            "outcome": None,
            "retry_feedback": list(feedback),
            "error_category": None,
            "surface_ok": None,
            "overall": None,
            "failed_requirements": [],
            "transcript_sha256": _get(generation_result, "transcript_sha256"),
            "reauthored_tests": [],
        }
        more_allowed = number < max_attempts
        current_hashes = {}

        if _get(generation_result, "refused"):
            entry["outcome"] = "refused"
            stop_reason = "refused"
        elif _get(generation_result, "files", {}):
            surface_report = deps.get("surface-checker").check_surface(component_id, repo_root)
            if not _get(surface_report, "ok"):
                entry["outcome"] = "surface_failed"
                entry["surface_ok"] = False
            else:
                entry["surface_ok"] = True
                verification_report = deps.get("verifier-orchestrator").verify(
                    component_id, repo_root, judge=judge, test_author=test_author)
                overall = _get(verification_report, "overall")
                entry["overall"] = overall
                if overall == "pass":
                    entry["outcome"] = "passed"
                    passed = True
                    stop_reason = "passed"
                    if mode == "single":
                        deps.get("generator").commit_cache(generation_result,
                                                           repo_root=repo_root)
                else:
                    entry["outcome"] = "verification_failed"
                    criteria = _get(verification_report, "criteria", [])
                    entry["failed_requirements"] = sorted({
                        _get(c, "covers") for c in criteria
                        if _get(c, "result") == "fail"
                        and _get(c, "failure_origin") not in ("test", "environment")
                    })
                    if any(_get(c, "failure_origin") == "environment" for c in criteria):
                        stop_reason = "environment"
                    current_hashes = _implementation_failure_hashes(
                        verification_report, repo_root, slug)
                    if stop_reason is None and more_allowed:
                        to_delete = sorted(
                            cid for cid, digest in current_hashes.items()
                            if prev_hashes.get(cid) == digest and cid not in reauthored_once)
                        for cid in to_delete:
                            _test_path(repo_root, slug, cid).unlink()
                            reauthored_once.add(cid)
                        entry["reauthored_tests"] = to_delete
        else:
            entry["outcome"] = "generation_failed"
            category = _get(_get(generation_result, "model_call_error"), "category")
            entry["error_category"] = category
            if category == "environment":
                stop_reason = "environment"
            elif category not in RETRIED_CATEGORIES:
                stop_reason = "not_retried"

        prev_hashes = current_hashes
        feedback = sorted(set(feedback) | set(entry["failed_requirements"]))
        attempts.append(entry)
        if on_attempt is not None:
            on_attempt(entry, generation_result, verification_report)
        if stop_reason is not None:
            break

    if stop_reason is None:
        stop_reason = "max_attempts"

    return AttemptLoopResult(
        passed=passed,
        stop_reason=stop_reason,
        attempts=attempts,
        generation_result=generation_result,
        verification_report=verification_report,
        surface_report=surface_report,
    )
