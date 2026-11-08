import os
import tempfile
import shutil
from pathlib import Path

import spec_completeness_assistant


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


SPEC_LINTER_MODULE = '''
def lint(paths, repo_root, strict=False, judge=None):
    return {
        "findings": [
            {
                "rule_id": "R-LINT-321",
                "severity": "warn",
                "file": "specs/components/foo/component.md",
                "line": 3,
                "message": "fake warn finding for AC-ASSIST-007",
            }
        ],
        "summary": {"hard_failures": 0, "warnings": 1, "skipped": 0},
    }
'''

IMPACT_ANALYZER_MODULE = '''
def compute_blast_radius(changed_ids, repo_root):
    return {
        "impacted": [
            {
                "component_id": "comp-foo",
                "reason": "direct",
                "via": None,
            }
        ],
        "precondition_error": None,
    }
'''

SPEC_BUNDLE_ASSEMBLER_MODULE = '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fakehash",
        "spec": "fake spec body",
        "interface": "fake interface body",
        "constraints": "fake constraints body",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fake glossary body",
        "hint_code": {"fake_file.py": "fake content"} if mode == "hint" else None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError("not used by this test")
'''

GENERATOR_MODULE = '''
import os


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    log_path = os.environ["ASSIST_TEST_CALL_LOG"]
    with open(log_path, "a") as f:
        f.write("generator.generate called\\n")
    component_id = bundle.get("component_id") if isinstance(bundle, dict) else getattr(bundle, "component_id", None)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fakehash",
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"fake_file.py": "fake content"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

LLM_ENDPOINT_MODULE = '''
import os


def complete(prompt, model, *, backend=None, **params):
    log_path = os.environ["ASSIST_TEST_CALL_LOG"]
    with open(log_path, "a") as f:
        f.write("llm_endpoint.complete called\\n")
    return {
        "text": "fake model output",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
'''


def _write_dependency(repo_root: Path, slug: str, module_name: str, content: str):
    dep_dir = repo_root / "gen" / slug
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / f"{module_name}.py").write_text(content)


def test_ac_assist_007_no_model_configured_skips_all_model_calls():
    tmp_dir = tempfile.mkdtemp(prefix="ac_assist_007_")
    try:
        repo_root = Path(tmp_dir) / "repo"
        repo_root.mkdir(parents=True)

        _write_dependency(repo_root, "spec-linter", "spec_linter", SPEC_LINTER_MODULE)
        _write_dependency(repo_root, "impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_MODULE)
        _write_dependency(
            repo_root,
            "spec-bundle-assembler",
            "spec_bundle_assembler",
            SPEC_BUNDLE_ASSEMBLER_MODULE,
        )
        _write_dependency(repo_root, "generator", "generator", GENERATOR_MODULE)
        _write_dependency(repo_root, "llm-endpoint", "llm_endpoint", LLM_ENDPOINT_MODULE)

        log_path = Path(tmp_dir) / "call_log.txt"
        os.environ["ASSIST_TEST_CALL_LOG"] = str(log_path)

        try:
            report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)
        finally:
            os.environ.pop("ASSIST_TEST_CALL_LOG", None)

        lint_findings = _get(report, "lint_findings")
        assert isinstance(lint_findings, list)
        assert len(lint_findings) == 1
        finding = lint_findings[0]
        assert _get(finding, "severity") == "warn"
        assert _get(finding, "rule_id") == "R-LINT-321"
        assert _get(finding, "message") == "fake warn finding for AC-ASSIST-007"

        predicted_blast_radius = _get(report, "predicted_blast_radius")
        assert predicted_blast_radius == ["comp-foo"]

        hint_previews = _get(report, "hint_previews")
        assert isinstance(hint_previews, dict)
        assert "comp-foo" in hint_previews
        assert hint_previews["comp-foo"] is not None

        assert _get(report, "degraded") is True
        assert _get(report, "completeness_score") is None
        assert _get(report, "completeness_rationale") is None
        assert _get(report, "redundancy_flags") == []

        if log_path.exists():
            log_contents = log_path.read_text()
        else:
            log_contents = ""
        assert "llm_endpoint.complete called" not in log_contents
        assert "generator.generate called" not in log_contents
        assert log_contents == ""
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)