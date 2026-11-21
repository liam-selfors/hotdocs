# hotdocs-criterion: sha256:50302db7be56b7bac97cb79cd6deadf9bee75f7029fa3f1cecfa2507521d3697
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ATTEMPT_KEYS = {
    "number",
    "outcome",
    "retry_feedback",
    "error_category",
    "failed_requirements",
    "transcript_sha256",
}


def manifest_paths(repo_root, slug):
    return [
        Path(repo_root) / "gen" / slug / ".provenance.json",
        Path(repo_root) / "verification" / slug / ".provenance.json",
    ]


def base_inputs(component_id):
    return {
        "component_id": component_id,
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }


def test_agentic_generation_and_attempt_history_filtered(tmp_path):
    component_id = "comp-foo"
    inputs = base_inputs(component_id)
    inputs["generation_result"] = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:b",
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        "mode": "agentic",
        "transcript_sha256": "sha256:t",
        "turns": 9,
        "tool_calls": 30,
        "isolation": "sandbox-exec",
        "transcript": "RAW-TRANSCRIPT",
    }
    inputs["gate_versions"] = {"generator": "generator@3.0.0+v11"}
    inputs["attempts"] = 2
    inputs["attempt_history"] = [
        {
            "number": 1,
            "outcome": "verification_failed",
            "retry_feedback": [],
            "error_category": None,
            "failed_requirements": ["R-FOO-002"],
            "transcript_sha256": "sha256:a1",
            "notes": "EXTRA-NOTE",
        },
        {
            "number": 2,
            "outcome": "passed",
            "retry_feedback": ["R-FOO-002"],
            "error_category": None,
            "failed_requirements": [],
            "transcript_sha256": "sha256:a2",
        },
    ]

    provenance_writer.write_provenance(component_id, inputs, tmp_path)

    for path in manifest_paths(tmp_path, "foo"):
        assert path.is_file(), str(path)
        text = path.read_text(encoding="utf-8")
        manifest = json.loads(text)

        assert manifest["generation"] == {
            "mode": "agentic",
            "generator_version": "generator@3.0.0+v11",
            "transcript_sha256": "sha256:t",
            "turns": 9,
            "tool_calls": 30,
            "isolation": "sandbox-exec",
        }
        assert manifest["attempts"] == 2
        history = manifest["attempt_history"]
        assert isinstance(history, list)
        assert len(history) == 2
        for entry in history:
            assert set(entry.keys()) == ATTEMPT_KEYS
        assert "RAW-TRANSCRIPT" not in text
        assert "EXTRA-NOTE" not in text


def test_absent_attempt_history_and_mode_default(tmp_path):
    component_id = "comp-bar"
    inputs = base_inputs(component_id)
    inputs["generation_result"] = {"files": {}}

    provenance_writer.write_provenance(component_id, inputs, tmp_path)

    for path in manifest_paths(tmp_path, "bar"):
        assert path.is_file(), str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["attempt_history"] == []
        assert manifest["generation"]["mode"] == "single"