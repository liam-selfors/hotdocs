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


def _get(obj, name):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _load(repo_root, slug):
    module = slug.replace("-", "_")
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


def _loader(repo_root):
    cache = {}

    def dep(slug):
        if slug not in cache:
            cache[slug] = _load(repo_root, slug)
        return cache[slug]

    return dep


def _jsonable(value):
    if value is None or isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if dataclasses.is_dataclass(value):
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
            "generation_result": _jsonable(self.generation_result),
            "verification_report": _jsonable(self.verification_report),
            "surface_report": _jsonable(self.surface_report),
        }


def _unwrap_fence(text):
    t = text.strip()
    m = re.match(r"^```[^\n]*\n(.*?)\n?```\s*$", t, re.S)
    if m:
        t = m.group(1)
    return t


def make_closures(model, seed, repo_root, llm_backend=None):
    dep = _loader(repo_root)

    def test_author(bundle):
        mod = dep("test-author")
        return mod.author_test(bundle, model, seed=seed, repo_root=repo_root,
                               llm_backend=llm_backend)

    def judge(bundle):
        mod = dep("llm-endpoint")
        slug = str(bundle["component_id"]).removeprefix("comp-")
        code_dir = Path(repo_root) / "gen" / slug
        parts = [
            "You are judging whether a component's code satisfies one acceptance criterion.",
            "",
            "## Criterion",
            str(bundle["criterion_text"]),
            "",
            "## Requirement",
            str(bundle["requirement_text"]),
            "",
            "## Interface",
            str(bundle["interface"]),
            "",
            "## Code",
        ]
        if code_dir.is_dir():
            for path in sorted(code_dir.rglob("*")):
                rel = path.relative_to(code_dir)
                if "__pycache__" in rel.parts or not path.is_file():
                    continue
                parts.append(f"### {rel.as_posix()}")
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
                parts.append("")
        parts.append('Reply with JSON only: {"result": "pass" | "fail", "rationale": "..."}')
        prompt = "\n".join(parts)
        response = mod.complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return {"result": "fail",
                    "rationale": f"judge unavailable: model call error {_get(error, 'category')}"}
        text = _get(response, "text") or ""
        try:
            data = json.loads(_unwrap_fence(str(text)))
        except ValueError:
            return {"result": "fail", "rationale": "judge unavailable: unparseable reply"}
        result = data.get("result") if isinstance(data, dict) else None
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": f"judge unavailable: invalid result {result!r}"}
        return {"result": result, "rationale": data.get("rationale")}

    return (test_author, judge)


def _test_path(repo_root, slug, criterion_id):
    name = "test_" + str(criterion_id).lower().replace("-", "_") + ".py"
    return Path(repo_root) / "verification" / slug / "generated-test" / name


def _impl_failure_hashes(report, repo_root, slug):
    hashes = {}
    for c in _get(report, "criteria") or []:
        if (_get(c, "kind") == "generated-test" and _get(c, "result") == "fail"
                and _get(c, "failure_origin") == "implementation"):
            path = _test_path(repo_root, slug, _get(c, "id"))
            if path.is_file():
                hashes[_get(c, "id")] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def run_attempts(component_id, bundle, repo_root, model, *, mode="single", max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    if mode not in ("single", "agentic"):
        raise ValueError(f"unknown mode: {mode!r}")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    dep = _loader(repo_root)
    test_author, judge = make_closures(model, seed, repo_root, llm_backend)
    slug = component_id.removeprefix("comp-")

    feedback = sorted(set(retry_feedback or []))
    attempts = []
    gen_result = None
    ver_report = None
    surf_report = None
    passed = False
    stop_reason = "max_attempts"
    prev_hashes = {}
    reauthored_done = set()

    for number in range(1, max_attempts + 1):
        fb_arg = list(feedback) or None
        if mode == "single":
            gen_result = dep("generator").generate(
                bundle, model, fb_arg, repo_root=repo_root, llm_backend=llm_backend)
        else:
            gen_result = dep("agentic-generator").generate_agentic(
                bundle, model, fb_arg, repo_root=repo_root,
                allow_unisolated_exec=allow_unisolated_exec)
        ver_report = None
        surf_report = None
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
        stop = None
        hashes = {}
        more = number < max_attempts

        if _get(gen_result, "refused"):
            entry["outcome"] = "refused"
            stop = "refused"
        elif _get(gen_result, "files"):
            surf_report = dep("surface-checker").check_surface(component_id, repo_root)
            if not _get(surf_report, "ok"):
                entry["outcome"] = "surface_failed"
                entry["surface_ok"] = False
            else:
                entry["surface_ok"] = True
                ver_report = dep("verifier-orchestrator").verify(
                    component_id, repo_root, judge=judge, test_author=test_author)
                overall = _get(ver_report, "overall")
                entry["overall"] = overall
                if overall == "pass":
                    entry["outcome"] = "passed"
                    stop = "passed"
                else:
                    entry["outcome"] = "verification_failed"
                    criteria = _get(ver_report, "criteria") or []
                    entry["failed_requirements"] = sorted({
                        _get(c, "covers") for c in criteria
                        if _get(c, "result") == "fail"
                        and _get(c, "failure_origin") not in ("test", "environment")
                    })
                    if any(_get(c, "failure_origin") == "environment" for c in criteria):
                        stop = "environment"
                    hashes = _impl_failure_hashes(ver_report, repo_root, slug)
                    if stop is None and more:
                        repeated = sorted(
                            cid for cid, h in hashes.items()
                            if prev_hashes.get(cid) == h and cid not in reauthored_done)
                        for cid in repeated:
                            _test_path(repo_root, slug, cid).unlink()
                            reauthored_done.add(cid)
                        entry["reauthored_tests"] = repeated
        else:
            entry["outcome"] = "generation_failed"
            category = _get(_get(gen_result, "model_call_error"), "category")
            entry["error_category"] = category
            if category == "environment":
                stop = "environment"
            elif category not in RETRIED_CATEGORIES:
                stop = "not_retried"

        attempts.append(entry)
        if on_attempt is not None:
            on_attempt(entry, gen_result, ver_report)

        if stop == "passed":
            passed = True
            if mode == "single":
                dep("generator").commit_cache(gen_result, repo_root=repo_root)
        if stop is not None:
            stop_reason = stop
            break

        feedback = sorted(set(feedback) | set(entry["failed_requirements"]))
        prev_hashes = hashes

    return AttemptLoopResult(
        passed=passed,
        stop_reason=stop_reason,
        attempts=attempts,
        generation_result=gen_result,
        verification_report=ver_report,
        surface_report=surf_report,
    )
