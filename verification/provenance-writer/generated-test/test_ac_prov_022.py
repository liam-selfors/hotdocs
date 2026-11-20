# hotdocs-criterion: sha256:af174c70dba1160801751786ae804eda2f1654deaa84258e8ca4d2644b8d28d3
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


def _base_generation_result():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:abc",
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def test_ac_prov_022_agentic_generation_and_attempt_history(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    generation_result = _base_generation_result()
    generation_result.update(
        {
            "mode": "agentic",
            "transcript_sha256": "sha256:t",
            "turns": 9,
            "tool_calls": 30,
            "isolation": "sandbox-exec",
            "transcript": "RAW-TRANSCRIPT",
        }
    )

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
        "component_id": "comp-foo",
        "generation_result": generation_result,
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": attempt_history,
        "gate_versions": {"generator": "generator@3.0.0+v11"},
    }

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    for path in _manifest_paths(repo_root, "foo"):
        assert path.is_file(), path
        raw = path.read_text(encoding="utf-8")
        assert "RAW-TRANSCRIPT" not in raw
        assert "EXTRA-NOTE" not in raw

        manifest = json.loads(raw)
        assert field(manifest, "generation") == {
            "mode": "agentic",
            "generator_version": "generator@3.0.0+v11",
            "transcript_sha256": "sha256:t",
            "turns": 9,
            "tool_calls": 30,
            "isolation": "sandbox-exec",
        }
        assert field(manifest, "attempts") == 2

        history = field(manifest, "attempt_history")
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


def test_ac_prov_022_defaults_without_history_or_mode(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    generation_result = _base_generation_result()

    inputs = {
        "component_id": "comp-foo",
        "generation_result": generation_result,
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    for path in _manifest_paths(repo_root, "foo"):
        assert path.is_file(), path
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert field(manifest, "attempt_history") == []
        generation = field(manifest, "generation")
        assert generation["mode"] == "single"