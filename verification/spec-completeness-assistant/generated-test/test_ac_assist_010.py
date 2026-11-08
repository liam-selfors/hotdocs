import json

import pytest

import spec_completeness_assistant


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _write_module(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


_SPEC_LINTER_SRC = '''
def lint(paths, repo_root, strict=False, judge=None):
    return {"findings": [], "summary": {"hard_failures": 0, "warnings": 0, "skipped": 0}}
'''

_IMPACT_ANALYZER_SRC = '''
def compute_blast_radius(changed_ids, repo_root):
    return {
        "impacted": [{"component_id": "comp-foo", "reason": "direct", "via": None}],
        "precondition_error": None,
    }
'''

_SPEC_BUNDLE_ASSEMBLER_SRC = '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fake",
        "spec": "fake spec",
        "interface": "fake interface",
        "constraints": "fake constraints",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fake glossary",
        "hint_code": {} if mode == "hint" else None,
    }
'''

_GENERATOR_SRC = '''
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = bundle.get("component_id") if isinstance(bundle, dict) else getattr(bundle, "component_id", None)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fake",
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"fake_file.py": "# fake"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_LLM_ENDPOINT_TEMPLATE = '''
import json

_RESPONSES = json.loads(open(__RESPONSES_PATH__).read())
_LOG_PATH = __LOG_PATH__
_STATE = {"n": 0}


def complete(prompt, model, *, backend=None, **params):
    idx = _STATE["n"]
    _STATE["n"] += 1
    with open(_LOG_PATH, "a") as f:
        f.write("call\\n")
    if idx < len(_RESPONSES):
        resp = _RESPONSES[idx]
    else:
        resp = {"text": None, "model_call_error": {"category": "network", "message": "no more fake responses"}}
    return {
        "text": resp.get("text"),
        "model": model,
        "backend": "fake-backend",
        "model_call_error": resp.get("model_call_error"),
    }
'''


def _setup_repo(tmp_path, llm_responses):
    repo_root = tmp_path / "repo"
    gen_dir = repo_root / "gen"

    _write_module(gen_dir / "spec-linter" / "spec_linter.py", _SPEC_LINTER_SRC)
    _write_module(gen_dir / "impact-analyzer" / "impact_analyzer.py", _IMPACT_ANALYZER_SRC)
    _write_module(gen_dir / "spec-bundle-assembler" / "spec_bundle_assembler.py", _SPEC_BUNDLE_ASSEMBLER_SRC)
    _write_module(gen_dir / "generator" / "generator.py", _GENERATOR_SRC)

    responses_path = tmp_path / "llm_responses.json"
    responses_path.write_text(json.dumps(llm_responses))
    log_path = tmp_path / "llm_calls.log"

    llm_src = _LLM_ENDPOINT_TEMPLATE.replace(
        "__RESPONSES_PATH__", repr(str(responses_path))
    ).replace(
        "__LOG_PATH__", repr(str(log_path))
    )
    _write_module(gen_dir / "llm-endpoint" / "llm_endpoint.py", llm_src)

    return repo_root, log_path


def test_completeness_and_redundancy_happy_path(tmp_path):
    responses = [
        {
            "text": "```json\n{\"completeness_score\": 0.7, \"completeness_rationale\": \"AC missing\"}\n```",
            "model_call_error": None,
        },
        {
            "text": json.dumps(
                {
                    "redundancy_flags": [
                        {
                            "new_requirement": "R-FOO-005",
                            "overlaps_with": "R-BAR-002",
                            "rationale": "Both require retry exhaustion to surface as a distinct failure mode.",
                        },
                        {
                            "new_requirement": "R-FOO-006",
                            "overlaps_with": "R-BAR-003",
                            "rationale": "",
                        },
                    ]
                }
            ),
            "model_call_error": None,
        },
    ]
    repo_root, log_path = _setup_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    call_count = log_path.read_text().count("call\n") if log_path.exists() else 0
    assert call_count == 2

    assert _get(report, "completeness_score") == 0.7
    assert _get(report, "completeness_rationale") == "AC missing"

    flags = _get(report, "redundancy_flags")
    assert len(flags) == 1
    entry = flags[0]
    assert _get(entry, "new_requirement") == "R-FOO-005"
    assert _get(entry, "overlaps_with") == "R-BAR-002"
    assert _get(entry, "rationale") == "Both require retry exhaustion to surface as a distinct failure mode."

    assert _get(report, "degraded") is False


def test_model_call_error_and_unparseable_text(tmp_path):
    responses = [
        {"text": None, "model_call_error": {"category": "network", "message": "connection reset"}},
        {"text": "this is not json at all", "model_call_error": None},
    ]
    repo_root, log_path = _setup_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    assert _get(report, "completeness_score") is None
    assert _get(report, "completeness_rationale") is None
    assert _get(report, "redundancy_flags") == []


def test_empty_rationale_does_not_parse(tmp_path):
    responses = [
        {"text": json.dumps({"completeness_score": 0.6, "completeness_rationale": ""}), "model_call_error": None},
        {"text": json.dumps({"redundancy_flags": []}), "model_call_error": None},
    ]
    repo_root, log_path = _setup_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    assert _get(report, "completeness_score") is None
    assert _get(report, "completeness_rationale") is None


@pytest.mark.parametrize(
    "completeness_text",
    [
        json.dumps({"completeness_rationale": "x"}),
        json.dumps({"completeness_score": True, "completeness_rationale": "x"}),
        "",
    ],
)
def test_malformed_completeness_shapes(tmp_path, completeness_text):
    responses = [
        {"text": completeness_text, "model_call_error": None},
        {"text": json.dumps({"redundancy_flags": []}), "model_call_error": None},
    ]
    repo_root, log_path = _setup_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    assert _get(report, "completeness_score") is None
    assert _get(report, "completeness_rationale") is None


def test_score_clamped_to_max(tmp_path):
    responses = [
        {
            "text": json.dumps({"completeness_score": 1.7, "completeness_rationale": "clamped"}),
            "model_call_error": None,
        },
        {"text": json.dumps({"redundancy_flags": []}), "model_call_error": None},
    ]
    repo_root, log_path = _setup_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    assert _get(report, "completeness_score") == 1.0