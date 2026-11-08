import json
from pathlib import Path

import pytest

import spec_completeness_assistant


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write_module(repo_root, slug, module_name, content):
    mod_dir = Path(repo_root) / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(content)


_SPEC_LINTER_TEMPLATE = '''
def lint(paths, repo_root, strict=False, judge=None):
    findings = __FINDINGS__
    hard = sum(1 for f in findings if f.get("severity") == "fail")
    warn = sum(1 for f in findings if f.get("severity") == "warn")
    skipped = sum(1 for f in findings if f.get("severity") == "skipped")
    return {
        "findings": findings,
        "summary": {"hard_failures": hard, "warnings": warn, "skipped": skipped},
    }
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
        "spec_bundle_hash": "sha256:fakehash",
        "spec": "",
        "interface": "",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": {} if mode == "hint" else None,
    }
'''

_GENERATOR_SRC = '''
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = bundle.get("component_id") if isinstance(bundle, dict) else getattr(bundle, "component_id", None)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fakehash",
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"fake.py": "# fake"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_LLM_ENDPOINT_TEMPLATE = '''
import json
import os

CALL_LOG = __CALL_LOG__

def complete(prompt, model, *, backend=None, **params):
    if os.path.exists(CALL_LOG):
        with open(CALL_LOG) as f:
            count = sum(1 for _ in f)
    else:
        count = 0
    with open(CALL_LOG, "a") as f:
        f.write(json.dumps({"model": model}) + "\\n")
    if count == 0:
        text = json.dumps({"completeness_score": 0.7, "completeness_rationale": "AC missing"})
    else:
        text = json.dumps({"redundancy_flags": []})
    return {
        "text": text,
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }
'''


def _setup_base_fakes(repo_root, lint_findings):
    spec_linter_src = _SPEC_LINTER_TEMPLATE.replace("__FINDINGS__", json.dumps(lint_findings))
    _write_module(repo_root, "spec-linter", "spec_linter", spec_linter_src)
    _write_module(repo_root, "impact-analyzer", "impact_analyzer", _IMPACT_ANALYZER_SRC)
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER_SRC)


def _setup_model_fakes(repo_root, call_log_path):
    _write_module(repo_root, "generator", "generator", _GENERATOR_SRC)
    llm_endpoint_src = _LLM_ENDPOINT_TEMPLATE.replace("__CALL_LOG__", json.dumps(str(call_log_path)))
    _write_module(repo_root, "llm-endpoint", "llm_endpoint", llm_endpoint_src)


_WARN_FINDING = {
    "rule_id": "R-LINT-003",
    "severity": "warn",
    "file": "specs/components/foo/component.md",
    "line": 12,
    "message": "depends_on references 'comp-bar', which looks unusual",
}

_FAIL_FINDING = {
    "rule_id": "R-LINT-003",
    "severity": "fail",
    "file": "specs/components/foo/component.md",
    "line": 12,
    "message": "depends_on references 'comp-bar', which does not exist",
}


def test_json_format_degraded_mode(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_base_fakes(repo_root, [_WARN_FINDING])

    rc = spec_completeness_assistant.main(
        ["--changed=R-FOO-001", f"--repo-root={repo_root}", "--format=json"]
    )
    captured = capsys.readouterr()

    assert rc == 0
    report = json.loads(captured.out)
    assert _get(report, "predicted_blast_radius") == ["comp-foo"]
    assert _get(report, "degraded") is True


def test_text_format_contains_rule_id_and_component(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_base_fakes(repo_root, [_WARN_FINDING])

    rc = spec_completeness_assistant.main(
        ["--changed", "R-FOO-001", "--repo-root", str(repo_root), "--format", "text"]
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "R-LINT-003" in captured.out
    assert "comp-foo" in captured.out


def test_model_scenario_json_then_text(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_base_fakes(repo_root, [_WARN_FINDING])
    call_log_path = repo_root / "_llm_calls.jsonl"
    _setup_model_fakes(repo_root, call_log_path)

    assert not call_log_path.exists()

    rc = spec_completeness_assistant.main(
        [
            "--changed=R-FOO-001",
            f"--repo-root={repo_root}",
            "--format=json",
            "--model=fake-model",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0

    assert call_log_path.exists()
    call_entries = [
        json.loads(line) for line in call_log_path.read_text().splitlines() if line.strip()
    ]
    assert len(call_entries) == 2
    for entry in call_entries:
        assert entry["model"] == "fake-model"

    report = json.loads(captured.out)
    assert _get(report, "degraded") is False
    assert _get(report, "completeness_score") == 0.7

    call_log_path.unlink()

    rc2 = spec_completeness_assistant.main(
        [
            "--changed=R-FOO-001",
            f"--repo-root={repo_root}",
            "--format=text",
            "--model=fake-model",
        ]
    )
    captured2 = capsys.readouterr()
    assert rc2 == 0
    assert "0.7" in captured2.out


def test_fail_severity_finding_exits_1(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_base_fakes(repo_root, [_FAIL_FINDING])

    rc = spec_completeness_assistant.main(
        ["--changed=R-FOO-001", f"--repo-root={repo_root}", "--format=json"]
    )

    assert rc == 1


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["serve", "--changed=R-FOO-001"],
        ["--format=json"],
        ["--changed=R-FOO-001", "--format=bogus"],
        ["--changed=R-FOO-001", "--unknown-flag=x"],
        ["--changed"],
    ],
)
def test_usage_errors_exit_2(argv):
    rc = spec_completeness_assistant.main(argv)
    assert rc == 2