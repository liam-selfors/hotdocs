"""AC-PROV-011 (Covers: R-PROV-011).

Given a completed write_provenance call
When the written file is parsed as JSON
Then parsing succeeds and its key set matches the schema exactly
"""

import json
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"

# SPEC_GUIDELINES.md section 7 field set, as reproduced in the provenance
# manifest interface document.
EXPECTED_KEYS = {
    "spec_bundle_hash",
    "model_pin",
    "prompt_version",
    "retry_feedback",
    "pipeline_version",
    "gate_versions",
    "provenance_hit",
    "generated_at",
    "verification_run_id",
    "verification_report",
    "license_scan",
    "secret_scan",
}

SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32


def _generation_result(with_files):
    if with_files:
        return {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": SPEC_BUNDLE_HASH,
            "model": "claude-sonnet-5",
            "prompt_version": "v10",
            "cache_hit": False,
            "files": {"foo.py": "def bar(x):\n    return x\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": ["R-FOO-003"],
        }
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "connection reset"},
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    }


def _license_scan_result():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan_result():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _inputs_fields(with_files):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(with_files),
        "verification_report": _verification_report() if with_files else None,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _build_inputs(fields):
    """Use the module's ProvenanceInputs type if it exposes one, else a dict."""
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and isinstance(cls, type) and cls is not dict:
        try:
            return cls(**fields)
        except TypeError:
            pass
    return dict(fields)


def _strict_parse(text):
    """Parse as strictly valid JSON: no NaN/Infinity, no duplicate keys."""

    def reject_constant(name):
        raise ValueError("non-standard JSON constant: %s" % name)

    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate keys in JSON object: %r" % keys)
        return dict(pairs)

    return json.loads(
        text, parse_constant=reject_constant, object_pairs_hook=no_duplicates
    )


@pytest.mark.parametrize("with_files", [True, False], ids=["verified", "never-verified"])
def test_written_manifest_is_valid_json_with_exact_schema_keys(tmp_path, with_files):
    repo_root = Path(tmp_path) / "repo"
    repo_root.mkdir()

    inputs = _build_inputs(_inputs_fields(with_files))

    # Given a completed write_provenance call
    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]

    for path in manifest_paths:
        assert path.is_file(), "expected manifest at %s" % path

        # When the written file is parsed as JSON
        text = path.read_text(encoding="utf-8")
        try:
            parsed = _strict_parse(text)
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            pytest.fail("manifest at %s is not valid JSON: %s" % (path, exc))

        # Then parsing succeeds and its key set matches the schema exactly
        assert isinstance(parsed, dict), "manifest top level must be a JSON object"
        actual_keys = set(parsed.keys())
        missing = EXPECTED_KEYS - actual_keys
        extra = actual_keys - EXPECTED_KEYS
        assert not missing, "manifest at %s is missing keys: %s" % (path, sorted(missing))
        assert not extra, "manifest at %s has extra keys: %s" % (path, sorted(extra))
        assert actual_keys == EXPECTED_KEYS