from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _has_key(obj, key):
    if isinstance(obj, dict):
        return key in obj
    return hasattr(obj, key)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_ac_assist_007_degraded_mode_no_model(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    log_path = repo_root / "call_log.jsonl"
    log_path_repr = repr(str(log_path))

    # Fake spec-linter: returns one "warn" finding.
    _write(
        repo_root / "gen" / "spec-linter" / "spec_linter.py",
        '''
def lint(paths, repo_root, strict=False, judge=None):
    return {
        "findings": [
            {
                "rule_id": "R-LINT-010",
                "severity": "warn",
                "file": "specs/components/foo/component.md",
                "line": 5,
                "message": "fixture warn finding",
                "rationale": None,
            }
        ],
        "summary": {"hard_failures": 0, "warnings": 1, "skipped": 0},
    }
''',
    )

    # Fake impact-analyzer: blast radius is comp-foo.
    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        '''
def compute_blast_radius(changed_ids, repo_root):
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None}
        ],
        "precondition_error": None,
    }
''',
    )

    # Fake spec-bundle-assembler: returns a hint-mode SpecBundle for comp-foo.
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fixture",
        "spec": "fixture spec text",
        "interface": "fixture interface text",
        "constraints": "fixture constraints text",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fixture glossary text",
        "hint_code": ({"fixture.py": "fixture code"} if mode == "hint" else None),
    }
''',
    )

    # Fake generator: MUST NOT be called when no model is configured.
    _write(
        repo_root / "gen" / "generator" / "generator.py",
        f'''
import json

_LOG_PATH = {log_path_repr}


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({{"caller": "generator"}}) + "\\n")
    return {{
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:fixture",
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {{"fixture.py": "fixture"}},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }}
''',
    )

    # Fake llm-endpoint: MUST NOT be called when no model is configured.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        f'''
import json

_LOG_PATH = {log_path_repr}


def complete(prompt, model, *, backend=None, **params):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({{"caller": "llm-endpoint"}}) + "\\n")
    return {{
        "text": "fixture response",
        "model": model,
        "backend": "fixture-backend",
        "model_call_error": None,
    }}
''',
    )

    import spec_completeness_assistant

    report = spec_completeness_assistant.assist(["comp-foo"], repo_root)

    lint_findings = _get(report, "lint_findings")
    assert len(lint_findings) == 1
    finding = lint_findings[0]
    assert _get(finding, "rule_id") == "R-LINT-010"
    assert _get(finding, "severity") == "warn"
    assert _get(finding, "file") == "specs/components/foo/component.md"
    assert _get(finding, "line") == 5
    assert _get(finding, "message") == "fixture warn finding"

    assert _get(report, "predicted_blast_radius") == ["comp-foo"]

    hint_previews = _get(report, "hint_previews")
    assert _has_key(hint_previews, "comp-foo")

    assert _get(report, "degraded") is True
    assert _get(report, "completeness_score") is None
    assert _get(report, "completeness_rationale") is None
    assert _get(report, "redundancy_flags") == []

    if log_path.exists():
        calls = [line for line in log_path.read_text().splitlines() if line.strip()]
        assert calls == []