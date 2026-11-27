# hotdocs-criterion: sha256:c644c7b860ca5ef1a88f02e4b20bc65a2d6376436e957475f488beb79fd5605f
import json
from pathlib import Path

import provenance_writer


ATTEMPT_KEYS = {
    "number",
    "outcome",
    "retry_feedback",
    "error_category",
    "failed_requirements",
    "transcript_sha256",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _manifest_paths(repo_root, slug):
    return [
        Path(repo_root) / "gen" / slug / ".provenance.json",
        Path(repo_root) / "verification" / slug / ".provenance.json",
    ]


def test_ac_prov_022_agentic_generation_and_attempt_history_filtered(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-foo"

    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:bundle",
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
    attempt_history = [
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
    inputs = {
        "component_id": component_id,
        "generation_result": generation_result,
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": attempt_history,
        "gate_versions": {"generator": "generator@3.0.0+v11"},
    }

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    for path in _manifest_paths(repo_root, "foo"):
        assert path.is_file(), str(path)
        text = path.read_text(encoding="utf-8")
        assert "RAW-TRANSCRIPT" not in text
        assert "EXTRA-NOTE" not in text
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
        assert history[0]["number"] == 1
        assert history[0]["outcome"] == "verification_failed"
        assert history[0]["failed_requirements"] == ["R-FOO-002"]
        assert history[0]["transcript_sha256"] == "sha256:a1"
        assert history[1]["number"] == 2
        assert history[1]["outcome"] == "passed"
        assert history[1]["retry_feedback"] == ["R-FOO-002"]
        assert history[1]["transcript_sha256"] == "sha256:a2"


def test_ac_prov_022_absent_history_and_mode_defaults(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-bar"

    inputs = {
        "component_id": component_id,
        "generation_result": {"files": {}},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    for path in _manifest_paths(repo_root, "bar"):
        assert path.is_file(), str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["attempt_history"] == []
        assert manifest["generation"]["mode"] == "single"
        assert manifest["generation"]["generator_version"] is None
        assert manifest["attempts"] == 1