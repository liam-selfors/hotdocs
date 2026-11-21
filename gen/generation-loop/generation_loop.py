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


def _get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load(slug, repo_root):
    module = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module}.py"
    name = f"_hotdocs_generation_loop_{module}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


class _Loader:
    def __init__(self, repo_root):
        self.repo_root = repo_root
        self.modules = {}

    def get(self, slug):
        if slug not in self.modules:
            self.modules[slug] = _load(slug, self.repo_root)
        return self.modules[slug]


def _json_form(value):
    if value is None:
        return None
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


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
            "generation_result": _json_form(self.generation_result),
            "verification_report": _json_form(self.verification_report),
            "surface_report": _json_form(self.surface_report),
        }


def _test_file(repo_root, slug, criterion_id):
    name = "test_" + str(criterion_id).lower().replace("-", "_") + ".py"
    return Path(repo_root) / "verification" / slug / "generated-test" / name


def _sha256(path):
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_attempts(component_id, bundle, repo_root, model, *, mode="single",
                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    if mode not in ("single", "agentic"):
        raise ValueError(f"unknown mode: {mode}")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    repo_root = Path(repo_root)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    loader = _Loader(repo_root)
    test_author, judge = make_closures(model, seed, repo_root, llm_backend)

    feedback = sorted(set(retry_feedback or []))
    attempts = []
    generation_result = None
    verification_report = None
    surface_report = None
    passed = False
    stop_reason = "max_attempts"
    prev_failing = {}
    reauthored_ids = set()

    for number in range(1, max_attempts + 1):
        feedback_arg = list(feedback) or None
        if mode == "single":
            result = loader.get("generator").generate(
                bundle, model, feedback_arg, repo_root=repo_root, llm_backend=llm_backend)
        else:
            result = loader.get("agentic-generator").generate_agentic(
                bundle, model, feedback_arg, repo_root=repo_root,
                allow_unisolated_exec=allow_unisolated_exec)

        generation_result = result
        verification_report = None
        surface_report = None
        entry = {
            "number": number,
            "outcome": None,
            "retry_feedback": list(feedback),
            "error_category": None,
            "surface_ok": None,
            "overall": None,
            "failed_requirements": [],
            "transcript_sha256": _get(result, "transcript_sha256"),
            "reauthored_tests": [],
        }
        stop = None
        has_more = number < max_attempts
        current_failing = {}
        files = _get(result, "files") or {}

        if _get(result, "refused") is not None:
            entry["outcome"] = "refused"
            stop = "refused"
        elif not files:
            entry["outcome"] = "generation_failed"
            category = _get(_get(result, "model_call_error"), "category")
            entry["error_category"] = category
            if category == "environment":
                stop = "environment"
            elif category not in RETRIED_CATEGORIES:
                stop = "not_retried"
        else:
            surface_report = loader.get("surface-checker").check_surface(component_id, repo_root)
            if not _get(surface_report, "ok"):
                entry["outcome"] = "surface_failed"
                entry["surface_ok"] = False
            else:
                entry["surface_ok"] = True
                verification_report = loader.get("verifier-orchestrator").verify(
                    component_id, repo_root, judge=judge, test_author=test_author)
                overall = _get(verification_report, "overall")
                entry["overall"] = overall
                criteria = _get(verification_report, "criteria") or []
                failed = set()
                environment = False
                for c in criteria:
                    origin = _get(c, "failure_origin")
                    if origin == "environment":
                        environment = True
                    if _get(c, "result") == "fail" and origin not in ("test", "environment"):
                        covers = _get(c, "covers")
                        if covers is not None:
                            failed.add(covers)
                    if (_get(c, "kind") == "generated-test" and _get(c, "result") == "fail"
                            and origin == "implementation"):
                        cid = _get(c, "id")
                        current_failing[cid] = _sha256(_test_file(repo_root, slug, cid))
                entry["failed_requirements"] = sorted(failed)
                if overall == "pass":
                    entry["outcome"] = "passed"
                    passed = True
                    stop = "passed"
                    if mode == "single":
                        loader.get("generator").commit_cache(result, repo_root=repo_root)
                else:
                    entry["outcome"] = "verification_failed"
                    if environment:
                        stop = "environment"
                    elif has_more:
                        deleted = []
                        for cid, digest in current_failing.items():
                            if (digest is not None and cid not in reauthored_ids
                                    and prev_failing.get(cid) == digest):
                                _test_file(repo_root, slug, cid).unlink()
                                reauthored_ids.add(cid)
                                deleted.append(cid)
                        entry["reauthored_tests"] = sorted(deleted)

        prev_failing = current_failing
        attempts.append(entry)
        if on_attempt is not None:
            on_attempt(entry, result, verification_report)

        if stop is not None:
            stop_reason = stop
            break
        feedback = sorted(set(feedback) | set(entry["failed_requirements"]))

    return AttemptLoopResult(
        passed=passed,
        stop_reason=stop_reason,
        attempts=attempts,
        generation_result=generation_result,
        verification_report=verification_report,
        surface_report=surface_report,
    )


def _unwrap_fence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def make_closures(model, seed, repo_root, llm_backend=None):
    repo_root = Path(repo_root)
    loaded = {}

    def _module(slug):
        if slug not in loaded:
            loaded[slug] = _load(slug, repo_root)
        return loaded[slug]

    def test_author(bundle):
        return _module("test-author").author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend)

    def judge(bundle):
        component_id = bundle["component_id"]
        slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
        code_dir = repo_root / "gen" / slug
        file_sections = []
        if code_dir.is_dir():
            for path in sorted(code_dir.rglob("*")):
                rel = path.relative_to(code_dir)
                if "__pycache__" in rel.parts or not path.is_file():
                    continue
                file_sections.append(
                    f"### File: {rel.as_posix()}\n\n{path.read_text(encoding='utf-8', errors='replace')}")
        prompt = (
            "You are judging whether a generated component's code satisfies one "
            "acceptance criterion.\n\n"
            "## Criterion\n\n" + str(bundle["criterion_text"]) + "\n\n"
            "## Requirement\n\n" + str(bundle["requirement_text"]) + "\n\n"
            "## Interface\n\n" + str(bundle["interface"]) + "\n\n"
            "## Code\n\n" + "\n\n".join(file_sections) + "\n\n"
            "Reply with only a JSON object: "
            '{"result": "pass" | "fail", "rationale": "..."}\n'
        )
        response = _module("llm-endpoint").complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error is not None:
            reason = _get(error, "category") or _get(error, "message") or "model call error"
            return {"result": "fail", "rationale": f"judge unavailable: {reason}"}
        text = _get(response, "text") or ""
        try:
            parsed = json.loads(_unwrap_fence(text))
            result = parsed.get("result")
            rationale = parsed.get("rationale", "")
        except (ValueError, AttributeError):
            return {"result": "fail", "rationale": "judge unavailable: unparseable reply"}
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": f"judge unavailable: invalid result {result!r}"}
        return {"result": result, "rationale": rationale}

    return (test_author, judge)
