import contextlib
import io
import json
import shutil
import tempfile
from pathlib import Path

import spec_completeness_assistant


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_module(repo_root, dep_slug, module_name, source):
    mod_dir = Path(repo_root) / "gen" / dep_slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(source)


_SPEC_LINTER_WARN = '''
def lint(paths, repo_root, strict=False, judge=None):
    return {
        "findings": [
            {
                "rule_id": "R-LINT-007",
                "severity": "warn",
                "file": "specs/components/foo/component.md",
                "line": 3,
                "message": "a warn finding for testing",
            }
        ],
        "summary": {"hard_failures": 0, "warnings": 1, "skipped": 0},
    }
'''

_SPEC_LINTER_FAIL = '''
def lint(paths, repo_root, strict=False, judge=None):
    return {
        "findings": [
            {
                "rule_id": "R-LINT-003",
                "severity": "fail",
                "file": "specs/components/foo/component.md",
                "line": 12,
                "message": "depends_on references 'comp-bar', which does not exist",
            }
        ],
        "summary": {"hard_failures": 1, "warnings": 0, "skipped": 0},
    }
'''

_IMPACT_ANALYZER = '''
def compute_blast_radius(changed_ids, repo_root=None):
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None}
        ],
        "precondition_error": None,
    }
'''

_SPEC_BUNDLE_ASSEMBLER = '''
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "spec": "fake spec text",
        "interface": "fake interface text",
        "constraints": "fake constraints text",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fake glossary text",
        "hint_code": {} if mode == "hint" else None,
    }


def assemble_criterion(component_id, criterion_id, repo_root=None):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
    }
'''

_GENERATOR = '''
def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    return {
        "component_id": _get(bundle, "component_id"),
        "spec_bundle_hash": _get(bundle, "spec_bundle_hash"),
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"stub.py": "# stub"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''


def _llm_endpoint_source(repo_root):
    log_path = str(Path(repo_root) / "llm_calls.log")
    count_path = str(Path(repo_root) / "llm_call_count.txt")
    return f'''
import json
from pathlib import Path

_LOG_PATH = {log_path!r}
_COUNT_PATH = {count_path!r}


def complete(prompt, model, *, backend=None, **params):
    count_file = Path(_COUNT_PATH)
    if count_file.exists():
        count = int(count_file.read_text()) + 1
    else:
        count = 1
    count_file.write_text(str(count))

    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({{"model": model, "backend": backend}}) + "\\n")

    if count % 2 == 1:
        text = json.dumps({{
            "completeness_score": 0.7,
            "completeness_rationale": "AC missing",
        }})
    else:
        text = json.dumps({{"redundancy_flags": []}})

    return {{
        "text": text,
        "model": model,
        "backend": "fake-backend",
        "model_call_error": None,
    }}
'''


def _build_repo_root(spec_linter_source):
    repo_root = Path(tempfile.mkdtemp())
    _write_module(repo_root, "spec-linter", "spec_linter", spec_linter_source)
    _write_module(repo_root, "impact-analyzer", "impact_analyzer", _IMPACT_ANALYZER)
    _write_module(
        repo_root, "spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER
    )
    _write_module(repo_root, "generator", "generator", _GENERATOR)
    _write_module(
        repo_root, "llm-endpoint", "llm_endpoint", _llm_endpoint_source(repo_root)
    )
    return repo_root


def _run_main(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = spec_completeness_assistant.main(argv)
    return rc, out.getvalue()


def test_degraded_mode_json_output():
    repo_root = _build_repo_root(_SPEC_LINTER_WARN)
    try:
        rc, output = _run_main(
            [
                "assist",
                "--changed=R-FOO-001",
                f"--repo-root={repo_root}",
                "--format=json",
            ]
        )
        assert rc == 0
        report = json.loads(output)
        assert _get(report, "predicted_blast_radius") == ["comp-foo"]
        assert _get(report, "degraded") is True
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)


def test_degraded_mode_text_output():
    repo_root = _build_repo_root(_SPEC_LINTER_WARN)
    try:
        rc, output = _run_main(
            [
                "assist",
                "--changed",
                "R-FOO-001",
                "--repo-root",
                str(repo_root),
                "--format",
                "text",
            ]
        )
        assert rc == 0
        assert "R-LINT-007" in output
        assert "comp-foo" in output
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)


def test_model_mode_json_then_text():
    repo_root = _build_repo_root(_SPEC_LINTER_WARN)
    try:
        rc, output = _run_main(
            [
                "assist",
                "--changed=R-FOO-001",
                f"--repo-root={repo_root}",
                "--format=json",
                "--model=fake-model",
            ]
        )
        assert rc == 0
        report = json.loads(output)
        assert _get(report, "degraded") is False
        assert _get(report, "completeness_score") == 0.7

        log_path = Path(repo_root) / "llm_calls.log"
        assert log_path.exists()
        calls = [json.loads(line) for line in log_path.read_text().splitlines() if line]
        assert len(calls) >= 1
        assert all(call["model"] == "fake-model" for call in calls)

        rc2, output2 = _run_main(
            [
                "assist",
                "--changed=R-FOO-001",
                f"--repo-root={repo_root}",
                "--format=text",
                "--model=fake-model",
            ]
        )
        assert rc2 == 0
        assert "0.7" in output2
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)


def test_fail_severity_returns_1():
    repo_root = _build_repo_root(_SPEC_LINTER_FAIL)
    try:
        rc, _output = _run_main(
            [
                "assist",
                "--changed=R-FOO-001",
                f"--repo-root={repo_root}",
                "--format=json",
            ]
        )
        assert rc == 1
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)


def test_usage_errors_return_2():
    repo_root = _build_repo_root(_SPEC_LINTER_WARN)
    try:
        # no --changed at all
        rc, _output = _run_main(
            ["assist", f"--repo-root={repo_root}", "--format=json"]
        )
        assert rc == 2

        # invalid --format value
        rc, _output = _run_main(
            [
                "assist",
                "--changed=R-FOO-001",
                f"--repo-root={repo_root}",
                "--format=bogus",
            ]
        )
        assert rc == 2

        # unknown argument
        rc, _output = _run_main(
            [
                "assist",
                "--changed=R-FOO-001",
                f"--repo-root={repo_root}",
                "--bogus-flag=value",
            ]
        )
        assert rc == 2

        # "--changed" given last with no value
        rc, _output = _run_main(
            ["assist", f"--repo-root={repo_root}", "--format=json", "--changed"]
        )
        assert rc == 2
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)