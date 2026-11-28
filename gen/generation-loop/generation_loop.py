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
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    here = Path(__file__).resolve()
    for d in here.parents:
        if d.name == "gen":
            return d.parent
    return here.parent.parent


def _load(repo_root, slug):
    module = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    if not d.is_dir():
        d = _tool_root() / "gen" / slug
    path = d / f"{module}.py"
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
            "generation_result": _plain(self.generation_result),
            "verification_report": _plain(self.verification_report),
            "surface_report": _plain(self.surface_report),
        }


def _test_path(repo_root, slug, criterion_id):
    name = "test_" + str(criterion_id).lower().replace("-", "_") + ".py"
    return Path(repo_root) / "verification" / slug / "generated-test" / name


def _impl_failed_test_hashes(report, repo_root, slug):
    hashes = {}
    for c in _get(report, "criteria") or []:
        if (_get(c, "kind") == "generated-test" and _get(c, "result") == "fail"
                and _get(c, "failure_origin") == "implementation"):
            cid = _get(c, "id")
            p = _test_path(repo_root, slug, cid)
            if p.is_file():
                hashes[cid] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def run_attempts(component_id, bundle, repo_root, model, *, mode="single",
                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    if mode not in ("single", "agentic"):
        raise ValueError(f"unknown mode: {mode}")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    repo_root = Path(repo_root)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id

    loaded = {}

    def dep(name):
        if name not in loaded:
            loaded[name] = _load(repo_root, name)
        return loaded[name]

    test_author, judge = make_closures(model, seed, repo_root, llm_backend)

    feedback = sorted(set(retry_feedback or []))
    attempts = []
    gen_result = None
    ver_report = None
    surf_report = None
    passed = False
    stop_reason = "max_attempts"
    prev_hashes = {}
    reauthored_once = set()

    for number in range(1, max_attempts + 1):
        fb_arg = list(feedback) or None
        if mode == "single":
            gr = dep("generator").generate(bundle, model, fb_arg, repo_root=repo_root,
                                           llm_backend=llm_backend)
        else:
            gr = dep("agentic-generator").generate_agentic(
                bundle, model, fb_arg, repo_root=repo_root,
                allow_unisolated_exec=allow_unisolated_exec)
        gen_result = gr
        ver_report = None
        surf_report = None

        error_category = None
        surface_ok = None
        overall = None
        failed = []
        stop = None
        hashes = {}

        mce = _get(gr, "model_call_error")
        if _get(gr, "refused"):
            outcome = "refused"
            stop = "refused"
        elif mce:
            outcome = "generation_failed"
            error_category = _get(mce, "category")
            if error_category == "environment":
                stop = "environment"
            elif error_category not in RETRIED_CATEGORIES:
                stop = "not_retried"
        else:
            sr = dep("surface-checker").check_surface(component_id, repo_root)
            surf_report = sr
            if not _get(sr, "ok"):
                outcome = "surface_failed"
                surface_ok = False
            else:
                surface_ok = True
                vr = dep("verifier-orchestrator").verify(
                    component_id, repo_root, judge=judge, test_author=test_author)
                ver_report = vr
                overall = _get(vr, "overall")
                criteria = _get(vr, "criteria") or []
                failed = sorted({
                    _get(c, "covers") for c in criteria
                    if _get(c, "result") == "fail"
                    and _get(c, "failure_origin") not in ("test", "environment")
                })
                hashes = _impl_failed_test_hashes(vr, repo_root, slug)
                if overall == "pass":
                    outcome = "passed"
                    stop = "passed"
                else:
                    outcome = "verification_failed"
                    if any(_get(c, "failure_origin") == "environment" for c in criteria):
                        stop = "environment"

        if stop is None and number == max_attempts:
            stop = "max_attempts"

        reauthored = []
        if outcome == "verification_failed" and stop is None:
            for cid, h in hashes.items():
                if cid not in reauthored_once and prev_hashes.get(cid) == h:
                    _test_path(repo_root, slug, cid).unlink()
                    reauthored_once.add(cid)
                    reauthored.append(cid)
            reauthored.sort()
        prev_hashes = hashes

        entry = {
            "number": number,
            "outcome": outcome,
            "retry_feedback": list(feedback),
            "error_category": error_category,
            "surface_ok": surface_ok,
            "overall": overall,
            "failed_requirements": failed,
            "transcript_sha256": _get(gr, "transcript_sha256"),
            "reauthored_tests": reauthored,
        }
        attempts.append(entry)

        if outcome == "passed":
            passed = True
            if mode == "single":
                dep("generator").commit_cache(gr, repo_root=repo_root)

        if on_attempt is not None:
            on_attempt(entry, gr, ver_report)

        feedback = sorted(set(feedback) | set(failed))

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


_FENCE = re.compile(r"^```[^\n]*\n(.*?)\n?```\s*$", re.S)


def _unavailable(reason):
    return {"result": "fail", "rationale": f"judge unavailable: {reason}"}


def make_closures(model, seed, repo_root, llm_backend=None):
    repo_root = Path(repo_root)

    def test_author(bundle):
        mod = _load(repo_root, "test-author")
        return mod.author_test(bundle, model, seed=seed, repo_root=repo_root,
                               llm_backend=llm_backend)

    def judge(bundle):
        component_id = bundle["component_id"]
        slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
        code_dir = repo_root / "gen" / slug
        file_parts = []
        for p in sorted(code_dir.rglob("*")):
            if "__pycache__" in p.relative_to(code_dir).parts or not p.is_file():
                continue
            rel = p.relative_to(code_dir).as_posix()
            text = p.read_text(encoding="utf-8", errors="replace")
            file_parts.append(f"### File: {rel}\n\n{text}")
        prompt = (
            "You are judging whether a component's generated code satisfies one "
            "acceptance criterion.\n\n"
            "## Criterion\n\n" + str(bundle["criterion_text"]) + "\n\n"
            "## Requirement\n\n" + str(bundle["requirement_text"]) + "\n\n"
            "## Interface\n\n" + str(bundle["interface"]) + "\n\n"
            "## Generated code\n\n" + "\n\n".join(file_parts) + "\n\n"
            "Reply with JSON only: "
            '{"result": "pass" | "fail", "rationale": "..."}\n'
        )
        mod = _load(repo_root, "llm-endpoint")
        resp = mod.complete(prompt, model, backend=llm_backend)
        err = _get(resp, "model_call_error")
        if err:
            return _unavailable(f"model call error: {_get(err, 'category')}")
        text = (_get(resp, "text") or "").strip()
        m = _FENCE.match(text)
        if m:
            text = m.group(1).strip()
        try:
            data = json.loads(text)
        except ValueError:
            return _unavailable("unparseable reply")
        result = data.get("result") if isinstance(data, dict) else None
        if result not in ("pass", "fail"):
            return _unavailable(f"invalid result: {result!r}")
        return {"result": result, "rationale": data.get("rationale")}

    return (test_author, judge)
