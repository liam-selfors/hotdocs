import json

import provenance_writer


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            },
            {
                "id": "AC-FOO-003",
                "covers": "R-FOO-003",
                "kind": "generated-test",
                "result": "fail",
                "failure_detail": {
                    "message": "result.foo equals 5 failed",
                    "expected": 5,
                    "actual": 3,
                },
                "test_authoring": {
                    "model": "gpt-5",
                    "seed": 0,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
            },
        ],
        "requirement_results": {
            "R-FOO-001": "pass",
            "R-FOO-002": "fail",
            "R-FOO-003": "fail",
        },
        "interface_drift": False,
        "mutation_score": 0.42,
        "overall": "fail",
    }


def test_verification_report_written_in_full_not_summarized(tmp_path):
    repo_root = tmp_path
    component_id = "comp-foo"
    slug = "foo"

    verification_report = _make_verification_report()

    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }

    license_scan_result = {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    inputs = {
        "component_id": component_id,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3",
        },
    }

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    gen_manifest_path = repo_root / "gen" / slug / ".provenance.json"
    verif_manifest_path = repo_root / "verification" / slug / ".provenance.json"

    assert gen_manifest_path.is_file()
    assert verif_manifest_path.is_file()

    gen_manifest = json.loads(gen_manifest_path.read_text())
    verif_manifest = json.loads(verif_manifest_path.read_text())

    for manifest in (gen_manifest, verif_manifest):
        written_report = _get(manifest, "verification_report")

        assert written_report == verification_report

        assert _get(written_report, "overall") == "fail"

        criteria = _get(written_report, "criteria")
        assert len(criteria) == 3

        third = criteria[2]
        assert _get(third, "failure_detail") == {
            "message": "result.foo equals 5 failed",
            "expected": 5,
            "actual": 3,
        }
        assert _get(third, "test_authoring") == {
            "model": "gpt-5",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
        }

        assert _get(written_report, "requirement_results") == {
            "R-FOO-001": "pass",
            "R-FOO-002": "fail",
            "R-FOO-003": "fail",
        }
        assert _get(written_report, "mutation_score") == 0.42
        assert _get(written_report, "interface_drift") is False