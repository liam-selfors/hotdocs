import spec_completeness_assistant as target


SPEC_LINTER_SOURCE = """
def lint(paths, repo_root, strict=False, judge=None):
    return {"findings": [], "summary": {"hard_failures": 0, "warnings": 0, "skipped": 0}}
"""

IMPACT_ANALYZER_SOURCE = """
def compute_blast_radius(changed_ids, repo_root):
    return {
        "impacted": [{"component_id": "comp-foo", "reason": "direct", "via": None}],
        "precondition_error": None,
    }
"""

SPEC_BUNDLE_ASSEMBLER_SOURCE = """
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fake",
        "spec": "fake spec text",
        "interface": "fake interface text",
        "constraints": "fake constraints text",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fake glossary text",
        "hint_code": {"stub.py": "# stub"} if mode == "hint" else None,
    }


def assemble_criterion(component_id, criterion_id, repo_root=None):
    raise NotImplementedError
"""

GENERATOR_SOURCE = """
def _field(bundle, key):
    if isinstance(bundle, dict):
        return bundle.get(key)
    return getattr(bundle, key, None)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    return {
        "component_id": _field(bundle, "component_id"),
        "spec_bundle_hash": _field(bundle, "spec_bundle_hash"),
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"stub.py": "# stub"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


def _llm_endpoint_source(log_path, completeness_text, completeness_error,
                          redundancy_text, redundancy_error):
    return f'''
LOG_PATH = {repr(str(log_path))}
COMPLETENESS_TEXT = {repr(completeness_text)}
COMPLETENESS_ERROR = {repr(completeness_error)}
REDUNDANCY_TEXT = {repr(redundancy_text)}
REDUNDANCY_ERROR = {repr(redundancy_error)}


def complete(prompt, model, *, backend=None, **params):
    with open(LOG_PATH, "r") as f:
        existing = f.readlines()
    call_number = len(existing) + 1
    with open(LOG_PATH, "a") as f:
        f.write(str(call_number) + chr(10))
    if call_number == 1:
        if COMPLETENESS_ERROR is not None:
            return {{"text": None, "model": model, "backend": "fake", "model_call_error": COMPLETENESS_ERROR}}
        return {{"text": COMPLETENESS_TEXT, "model": model, "backend": "fake", "model_call_error": None}}
    else:
        if REDUNDANCY_ERROR is not None:
            return {{"text": None, "model": model, "backend": "fake", "model_call_error": REDUNDANCY_ERROR}}
        return {{"text": REDUNDANCY_TEXT, "model": model, "backend": "fake", "model_call_error": None}}
'''


def _write_module(repo_root, slug, module_name, source):
    module_dir = repo_root / "gen" / slug
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / f"{module_name}.py").write_text(source)


def _write_fixed_dependencies(repo_root):
    _write_module(repo_root, "spec-linter", "spec_linter", SPEC_LINTER_SOURCE)
    _write_module(repo_root, "impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_SOURCE)
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SOURCE)
    _write_module(repo_root, "generator", "generator", GENERATOR_SOURCE)


def _write_llm_endpoint(repo_root, log_path, completeness_text=None, completeness_error=None,
                         redundancy_text=None, redundancy_error=None):
    log_path.write_text("")
    source = _llm_endpoint_source(
        log_path, completeness_text, completeness_error, redundancy_text, redundancy_error
    )
    _write_module(repo_root, "llm-endpoint", "llm_endpoint", source)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_assist_two_valid_responses_fenced_completeness_and_redundancy(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixed_dependencies(repo_root)

    log_path = tmp_path / "llm_calls.log"
    completeness_text = (
        '```json\n{"completeness_score": 0.7, "completeness_rationale": "AC missing"}\n```'
    )
    redundancy_text = (
        '{"redundancy_flags": ['
        '{"new_requirement": "R-FOO-005", "overlaps_with": "R-BAR-002", '
        '"rationale": "Both require retry exhaustion to surface distinctly."}, '
        '{"new_requirement": "R-FOO-006", "overlaps_with": "R-BAR-003", "rationale": ""}'
        ']}'
    )
    _write_llm_endpoint(
        repo_root, log_path,
        completeness_text=completeness_text,
        redundancy_text=redundancy_text,
    )

    report = target.assist(["R-FOO-003"], repo_root, model="fake-model")

    with open(log_path, "r") as f:
        call_lines = f.readlines()
    assert len(call_lines) == 2

    assert _get(report, "completeness_score") == 0.7
    assert _get(report, "completeness_rationale") == "AC missing"

    redundancy_flags = _get(report, "redundancy_flags")
    assert len(redundancy_flags) == 1
    entry = redundancy_flags[0]
    assert _get(entry, "new_requirement") == "R-FOO-005"
    assert _get(entry, "overlaps_with") == "R-BAR-002"
    assert _get(entry, "rationale") == "Both require retry exhaustion to surface distinctly."

    assert _get(report, "degraded") is False


def test_assist_model_call_error_and_unparseable_text(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixed_dependencies(repo_root)

    log_path = tmp_path / "llm_calls.log"
    _write_llm_endpoint(
        repo_root, log_path,
        completeness_error={"category": "network", "message": "simulated network failure"},
        redundancy_text="this is not json at all, {broken",
    )

    report = target.assist(["R-FOO-003"], repo_root, model="fake-model")

    assert _get(report, "completeness_score") is None
    assert _get(report, "completeness_rationale") is None
    assert _get(report, "redundancy_flags") == []


def test_assist_completeness_empty_rationale_rejected(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixed_dependencies(repo_root)

    log_path = tmp_path / "llm_calls.log"
    _write_llm_endpoint(
        repo_root, log_path,
        completeness_text='{"completeness_score": 0.6, "completeness_rationale": ""}',
        redundancy_text='{"redundancy_flags": []}',
    )

    report = target.assist(["R-FOO-003"], repo_root, model="fake-model")

    assert _get(report, "completeness_score") is None
    assert _get(report, "completeness_rationale") is None


def test_assist_completeness_score_clamped_above_range(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixed_dependencies(repo_root)

    log_path = tmp_path / "llm_calls.log"
    _write_llm_endpoint(
        repo_root, log_path,
        completeness_text='{"completeness_score": 1.7, "completeness_rationale": "valid rationale"}',
        redundancy_text='{"redundancy_flags": []}',
    )

    report = target.assist(["R-FOO-003"], repo_root, model="fake-model")

    assert _get(report, "completeness_score") == 1.0