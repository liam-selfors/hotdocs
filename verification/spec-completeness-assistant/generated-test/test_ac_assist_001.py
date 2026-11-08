import os
import textwrap
from pathlib import Path

import spec_completeness_assistant


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _write_module(repo_root, slug, module_name, source):
    mod_dir = Path(repo_root) / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / (module_name + ".py")).write_text(source)


def _make_repo_root(tmp_path, lint_findings, suffix):
    repo_root = tmp_path / ("repo_" + suffix)
    repo_root.mkdir()

    lint_template = textwrap.dedent('''
        _FINDINGS = __FINDINGS__

        def lint(paths, repo_root, strict=False, judge=None):
            return {
                "findings": _FINDINGS,
                "summary": {
                    "hard_failures": sum(1 for x in _FINDINGS if x["severity"] == "fail"),
                    "warnings": sum(1 for x in _FINDINGS if x["severity"] == "warn"),
                    "skipped": sum(1 for x in _FINDINGS if x["severity"] == "skipped"),
                },
            }
    ''')
    lint_source = lint_template.replace("__FINDINGS__", repr(lint_findings))
    _write_module(repo_root, "spec-linter", "spec_linter", lint_source)

    impact_source = textwrap.dedent('''
        import os

        def compute_blast_radius(changed_ids, repo_root):
            log_path = os.environ["ASSIST_TEST_LOG"]
            with open(log_path, "a") as f:
                f.write("impact-analyzer\\n")
            return {"impacted": [], "precondition_error": None}
    ''')
    _write_module(repo_root, "impact-analyzer", "impact_analyzer", impact_source)

    assemble_source = textwrap.dedent('''
        import os

        def assemble(component_id, repo_root, mode="cold"):
            log_path = os.environ["ASSIST_TEST_LOG"]
            with open(log_path, "a") as f:
                f.write("spec-bundle-assembler\\n")
            return {
                "component_id": component_id,
                "spec_bundle_hash": "sha256:fake",
                "spec": "",
                "interface": "",
                "constraints": "",
                "dependency_interfaces": {},
                "dependency_context": {},
                "dependency_usage": {},
                "vars": {},
                "glossary": "",
                "hint_code": {},
            }
    ''')
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", assemble_source)

    generator_source = textwrap.dedent('''
        import os

        def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
            log_path = os.environ["ASSIST_TEST_LOG"]
            with open(log_path, "a") as f:
                f.write("generator\\n")
            component_id = bundle.get("component_id") if isinstance(bundle, dict) else getattr(bundle, "component_id", None)
            return {
                "component_id": component_id,
                "spec_bundle_hash": "sha256:fake",
                "model": model,
                "prompt_version": "v1",
                "cache_hit": False,
                "files": {"fake.py": "# fake"},
                "model_call_error": None,
                "refused": None,
                "retry_feedback": retry_feedback,
            }
    ''')
    _write_module(repo_root, "generator", "generator", generator_source)

    llm_endpoint_source = textwrap.dedent('''
        import os
        import json

        def complete(prompt, model, *, backend=None, **params):
            log_path = os.environ["ASSIST_TEST_LOG"]
            with open(log_path, "a") as f:
                f.write("llm-endpoint\\n")
            return {
                "text": json.dumps({"score": 1.0, "rationale": "fake", "flags": []}),
                "model": model,
                "backend": "fake",
                "model_call_error": None,
            }
    ''')
    _write_module(repo_root, "llm-endpoint", "llm_endpoint", llm_endpoint_source)

    return repo_root


def test_assist_stops_immediately_on_fail_severity_lint_finding(tmp_path):
    log_path = tmp_path / "fail_case_log.txt"
    log_path.write_text("")

    finding = {
        "rule_id": "R-LINT-003",
        "severity": "fail",
        "file": "specs/components/foo/component.md",
        "line": 12,
        "message": "depends_on references 'comp-bar', which does not exist",
    }
    repo_root = _make_repo_root(tmp_path, [finding], "fail")

    os.environ["ASSIST_TEST_LOG"] = str(log_path)
    try:
        report = spec_completeness_assistant.assist(
            ["R-FOO-001"], repo_root, model="fake-model"
        )
    finally:
        del os.environ["ASSIST_TEST_LOG"]

    assert _field(report, "lint_findings") == [finding]
    assert _field(report, "predicted_blast_radius") == []
    assert _field(report, "hint_previews") == {}
    assert _field(report, "completeness_score") is None
    assert _field(report, "completeness_rationale") is None
    assert _field(report, "redundancy_flags") == []

    log_lines = log_path.read_text().splitlines()
    assert "impact-analyzer" not in log_lines
    assert "spec-bundle-assembler" not in log_lines
    assert "generator" not in log_lines
    assert "llm-endpoint" not in log_lines


def test_assist_proceeds_past_linting_on_warn_only_finding(tmp_path):
    log_path = tmp_path / "warn_case_log.txt"
    log_path.write_text("")

    finding = {
        "rule_id": "R-LINT-009",
        "severity": "warn",
        "file": "specs/components/foo/component.md",
        "line": 5,
        "message": "a non-blocking style nit",
    }
    repo_root = _make_repo_root(tmp_path, [finding], "warn")

    os.environ["ASSIST_TEST_LOG"] = str(log_path)
    try:
        try:
            spec_completeness_assistant.assist(
                ["R-FOO-001"], repo_root, model="fake-model"
            )
        except Exception:
            pass
    finally:
        del os.environ["ASSIST_TEST_LOG"]

    log_lines = log_path.read_text().splitlines()
    assert "impact-analyzer" in log_lines