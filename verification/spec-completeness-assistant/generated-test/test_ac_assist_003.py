import json

import spec_completeness_assistant


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


SPEC_LINTER_SRC = '''
import json
import os


def lint(paths, repo_root, strict=False, judge=None):
    log_path = os.environ["ASSIST_TEST_LOG"]
    with open(log_path, "a") as f:
        f.write(json.dumps({"module": "spec-linter", "func": "lint"}) + "\\n")
    return {"findings": [], "summary": {"hard_failures": 0, "warnings": 0, "skipped": 0}}
'''

IMPACT_ANALYZER_SRC = '''
import json
import os


def compute_blast_radius(changed_ids, repo_root):
    log_path = os.environ["ASSIST_TEST_LOG"]
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "module": "impact-analyzer",
            "func": "compute_blast_radius",
            "changed_ids": list(changed_ids),
        }) + "\\n")
    return {
        "impacted": [{"component_id": "comp-foo", "reason": "direct", "via": None}],
        "precondition_error": None,
    }
'''

ASSEMBLER_SRC = '''
import json
import os


def assemble(component_id, repo_root, mode="cold"):
    log_path = os.environ["ASSIST_TEST_LOG"]
    spec_bundle_hash = "sha256:fakehash-" + component_id
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "module": "spec-bundle-assembler",
            "func": "assemble",
            "component_id": component_id,
            "mode": mode,
            "spec_bundle_hash": spec_bundle_hash,
        }) + "\\n")
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "spec": "",
        "interface": "",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": {"spec_completeness_assistant.py": "# fake hint code"} if mode == "hint" else None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError
'''

GENERATOR_SRC = '''
import json
import os


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    log_path = os.environ["ASSIST_TEST_LOG"]
    component_id = bundle.get("component_id") if isinstance(bundle, dict) else getattr(bundle, "component_id", None)
    spec_bundle_hash = bundle.get("spec_bundle_hash") if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash", None)
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "module": "generator",
            "func": "generate",
            "component_id": component_id,
            "spec_bundle_hash": spec_bundle_hash,
            "model": model,
        }) + "\\n")
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"spec_completeness_assistant.py": "# fake generated content"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

LLM_ENDPOINT_SRC = '''
import json
import os


def complete(prompt, model, *, backend=None, **params):
    log_path = os.environ["ASSIST_TEST_LOG"]
    with open(log_path, "a") as f:
        f.write(json.dumps({"module": "llm-endpoint", "func": "complete", "model": model}) + "\\n")
    text = json.dumps({"score": 0.9, "rationale": "fake rationale", "flags": []})
    return {"text": text, "model": model, "backend": "fake-backend", "model_call_error": None}
'''


def _write_fake_deps(repo_root):
    deps = {
        "spec-linter": ("spec_linter.py", SPEC_LINTER_SRC),
        "impact-analyzer": ("impact_analyzer.py", IMPACT_ANALYZER_SRC),
        "spec-bundle-assembler": ("spec_bundle_assembler.py", ASSEMBLER_SRC),
        "generator": ("generator.py", GENERATOR_SRC),
        "llm-endpoint": ("llm_endpoint.py", LLM_ENDPOINT_SRC),
    }
    for slug, (filename, src) in deps.items():
        mod_dir = repo_root / "gen" / slug
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / filename).write_text(src)


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = log_path.read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_hint_preview_with_model_calls_generate(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fake_deps(repo_root)

    log_path = tmp_path / "log.jsonl"
    monkeypatch.setenv("ASSIST_TEST_LOG", str(log_path))

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    hint_previews = _get(report, "hint_previews")
    assert isinstance(hint_previews, dict)
    assert set(hint_previews.keys()) == {"comp-foo"}

    entries = _read_log(log_path)

    assemble_entries = [e for e in entries if e["module"] == "spec-bundle-assembler"]
    assert len(assemble_entries) == 1
    assert assemble_entries[0]["component_id"] == "comp-foo"
    assert assemble_entries[0]["mode"] == "hint"
    assert all(e["mode"] != "cold" for e in assemble_entries)

    generate_entries = [e for e in entries if e["module"] == "generator"]
    assert len(generate_entries) == 1
    assert generate_entries[0]["component_id"] == "comp-foo"
    assert generate_entries[0]["spec_bundle_hash"] == assemble_entries[0]["spec_bundle_hash"]


def test_hint_preview_without_model_skips_generate(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fake_deps(repo_root)

    log_path = tmp_path / "log.jsonl"
    monkeypatch.setenv("ASSIST_TEST_LOG", str(log_path))

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    hint_previews = _get(report, "hint_previews")
    assert isinstance(hint_previews, dict)
    assert set(hint_previews.keys()) == {"comp-foo"}

    entries = _read_log(log_path)

    assemble_entries = [e for e in entries if e["module"] == "spec-bundle-assembler"]
    assert len(assemble_entries) == 1
    assert assemble_entries[0]["component_id"] == "comp-foo"
    assert assemble_entries[0]["mode"] == "hint"

    generate_entries = [e for e in entries if e["module"] == "generator"]
    assert len(generate_entries) == 0