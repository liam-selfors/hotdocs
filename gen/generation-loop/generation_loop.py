"""Generation loop: bounded generate / surface-check / verify attempts."""

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_dep(repo_root, slug):
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
        self._mods = {}

    def get(self, slug):
        if slug not in self._mods:
            self._mods[slug] = _load_dep(self._repo_root, slug)
        return self._mods[slug]


def _as_json(obj):
    if obj is None or isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj):
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
            "generation_result": _as_json(self.generation_result),
            "verification_report": _as_json(self.verification_report),
            "surface_report": _as_json(self.surface_report),
        }


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _test_file(repo_root, slug, criterion_id):
    name = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    return Path(repo_root) / "verification" / slug / "generated-test" / name


def _impl_failure_hashes(repo_root, slug, criteria):
    hashes = {}
    for c in criteria:
        if (_get(c, "kind") == "generated-test" and _get(c, "result") == "fail"
                and _get(c, "failure_origin") == "implementation"):
            cid = _get(c, "id")
            path = _test_file(repo_root, slug, cid)
            hashes[cid] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return hashes


def run_attempts(component_id, bundle, repo_root, model, *, mode="single", max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    if mode not in ("single", "agentic"):
        raise ValueError(f"unknown mode: {mode!r}")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    deps = _Deps(repo_root)
    slug = _slug(component_id)
    test_author, judge = make_closures(model, seed, repo_root, llm_backend)

    feedback = sorted(set(retry_feedback or []))
    attempts = []
    reauthored_done = set()
    prev_hashes = None
    passed = False
    stop_reason = "max_attempts"
    gen = None
    report = None
    surface = None

    for number in range(1, max_attempts + 1):
        fb_arg = list(feedback) if feedback else None
        if mode == "single":
            gen = deps.get("generator").generate(
                bundle, model, fb_arg, repo_root=repo_root, llm_backend=llm_backend)
        else:
            gen = deps.get("agentic-generator").generate_agentic(
                bundle, model, fb_arg, repo_root=repo_root,
                allow_unisolated_exec=allow_unisolated_exec)

        report = None
        surface = None
        entry = {
            "number": number,
            "outcome": None,
            "retry_feedback": list(feedback),
            "error_category": None,
            "surface_ok": None,
            "overall": None,
            "failed_requirements": [],
            "transcript_sha256": _get(gen, "transcript_sha256"),
            "reauthored_tests": [],
        }
        stop = None
        hashes = None
        is_last = number == max_attempts

        if _get(gen, "refused"):
            entry["outcome"] = "refused"
            stop = "refused"
        elif not (_get(gen, "files") or {}):
            entry["outcome"] = "generation_failed"
            category = _get(_get(gen, "model_call_error"), "category")
            entry["error_category"] = category
            if category == "environment":
                stop = "environment"
            elif category not in RETRIED_CATEGORIES:
                stop = "not_retried"
        else:
            surface = deps.get("surface-checker").check_surface(component_id, repo_root)
            if not _get(surface, "ok"):
                entry["outcome"] = "surface_failed"
                entry["surface_ok"] = False
            else:
                entry["surface_ok"] = True
                report = deps.get("verifier-orchestrator").verify(
                    component_id, repo_root, judge=judge, test_author=test_author)
                overall = _get(report, "overall")
                entry["overall"] = overall
                criteria = _get(report, "criteria") or []
                if overall == "pass":
                    entry["outcome"] = "passed"
                    stop = "passed"
                else:
                    entry["outcome"] = "verification_failed"
                    entry["failed_requirements"] = sorted({
                        _get(c, "covers") for c in criteria
                        if _get(c, "result") == "fail"
                        and _get(c, "failure_origin") not in ("test", "environment")
                    })
                    if any(_get(c, "failure_origin") == "environment" for c in criteria):
                        stop = "environment"
                    hashes = _impl_failure_hashes(repo_root, slug, criteria)
                    if stop is None and not is_last and prev_hashes is not None:
                        repeat = sorted(
                            cid for cid, h in hashes.items()
                            if h is not None and prev_hashes.get(cid) == h
                            and cid not in reauthored_done
                        )
                        for cid in repeat:
                            _test_file(repo_root, slug, cid).unlink()
                            reauthored_done.add(cid)
                        entry["reauthored_tests"] = repeat

        attempts.append(entry)
        if on_attempt is not None:
            on_attempt(entry, gen, report)

        if stop == "passed":
            passed = True
            if mode == "single":
                deps.get("generator").commit_cache(gen, repo_root=repo_root)
        prev_hashes = hashes
        feedback = sorted(set(feedback) | set(entry["failed_requirements"]))
        if stop is not None:
            stop_reason = stop
            break

    return AttemptLoopResult(
        passed=passed,
        stop_reason=stop_reason,
        attempts=attempts,
        generation_result=gen,
        verification_report=report,
        surface_report=surface,
    )


_FENCE = re.compile(r"^```[^\n]*\n(.*?)\n?```\s*$", re.DOTALL)


def make_closures(model, seed, repo_root, llm_backend=None):
    mods = {}

    def _dep(slug):
        if slug not in mods:
            mods[slug] = _load_dep(repo_root, slug)
        return mods[slug]

    def test_author(bundle):
        return _dep("test-author").author_test(
            bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend)

    def judge(bundle):
        slug = _slug(bundle["component_id"])
        code_dir = Path(repo_root) / "gen" / slug
        parts = []
        if code_dir.is_dir():
            for path in sorted(code_dir.rglob("*")):
                rel = path.relative_to(code_dir)
                if "__pycache__" in rel.parts or not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                parts.append(f"### File: {rel.as_posix()}\n{text}")
        prompt = (
            "You are judging whether a component's code satisfies one acceptance "
            "criterion.\n\n"
            f"## Criterion\n{bundle['criterion_text']}\n\n"
            f"## Requirement\n{bundle['requirement_text']}\n\n"
            f"## Interface\n{bundle['interface']}\n\n"
            "## Code\n" + "\n\n".join(parts) + "\n\n"
            'Reply with JSON only: {"result": "pass" | "fail", "rationale": "..."}\n'
        )
        response = _dep("llm-endpoint").complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return {"result": "fail",
                    "rationale": f"judge unavailable: model call error: {_get(error, 'category')}"}
        text = (_get(response, "text") or "").strip()
        match = _FENCE.match(text)
        if match:
            text = match.group(1).strip()
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return {"result": "fail", "rationale": "judge unavailable: unparseable reply"}
        result = data.get("result") if isinstance(data, dict) else None
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": f"judge unavailable: invalid result {result!r}"}
        return {"result": result, "rationale": data.get("rationale")}

    return (test_author, judge)
