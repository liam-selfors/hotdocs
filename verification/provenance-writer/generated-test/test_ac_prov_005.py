"""AC-PROV-005: a failing VerificationReport is copied into the manifest in full.

Given a VerificationReport with overall "fail"
When write_provenance runs
Then verification_report in the manifest contains that full report, not a
  summary of it.
"""

import copy
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _build_failing_report():
    """A large, detail-rich VerificationReport whose overall verdict is fail.

    It is deliberately big and carries every per-kind detail field
    (failure_detail, rationale, test_authoring) plus long free-text
    messages, so that any summarizing, truncating or field-dropping
    shows up as a mismatch.
    """
    long_message = (
        "result.widget_count equals 5 failed; "
        + "context line with detail that must survive verbatim. " * 60
    ).strip()
    criteria = []
    requirement_results = {}
    for i in range(1, 31):
        crit_id = "AC-WIDGET-%03d" % i
        req_id = "R-WIDGET-%03d" % i
        if i % 3 == 1:
            entry = {
                "id": crit_id,
                "covers": req_id,
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {
                    "message": "%s #%d" % (long_message, i),
                    "expected": {"widgets": [1, 2, 3, i], "nested": {"deep": [i, {"k": "v"}]}},
                    "actual": {"widgets": [1, 2], "nested": {"deep": [0, {"k": "w"}]}},
                },
            }
            requirement_results[req_id] = "fail"
        elif i % 3 == 2:
            entry = {
                "id": crit_id,
                "covers": req_id,
                "kind": "llm-judge",
                "result": "skipped" if i % 2 == 0 else "pass",
                "rationale": None if i % 2 == 0 else "Judge rationale for %s: " % crit_id + "x" * 500,
            }
            requirement_results[req_id] = "fail" if i % 2 == 0 else "pass"
        else:
            entry = {
                "id": crit_id,
                "covers": req_id,
                "kind": "generated-test",
                "result": "fail" if i % 2 == 0 else "pass",
                "test_authoring": {
                    "model": "claude-sonnet-5",
                    "seed": i,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
            }
            if entry["result"] == "fail":
                entry["failure_detail"] = {
                    "message": "generated test %s failed: %s" % (crit_id, long_message),
                    "expected": "alpha-%d" % i,
                    "actual": None,
                }
                requirement_results[req_id] = "fail"
            else:
                requirement_results[req_id] = "pass"
        criteria.append(entry)

    return {
        "component_id": COMPONENT_ID,
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": True,
        "mutation_score": 0.4375,
        "overall": "fail",
    }


def _build_inputs(report):
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget_maker.py": "def make_widget(n):\n    return n\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-WIDGET-001"],
    }
    license_scan_result = {
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
    secret_scan_result = {
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
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def test_failing_verification_report_is_recorded_in_full(tmp_path):
    repo_root = Path(tmp_path)
    # Lay out the generated candidate the manifest describes.
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text("def make_widget(n):\n    return n\n")
    (repo_root / "verification" / SLUG).mkdir(parents=True, exist_ok=True)

    report = _build_failing_report()
    assert report["overall"] == "fail"
    # The JSON form of the report, independent of anything the writer does.
    expected_report = json.loads(json.dumps(copy.deepcopy(report)))

    inputs = _build_inputs(report)
    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    for path in manifest_paths:
        assert path.is_file(), "manifest missing at %s" % path
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict)
        assert "verification_report" in manifest, path

        recorded = manifest["verification_report"]
        assert isinstance(recorded, dict), (
            "verification_report must be the full report object, not a summary: %r"
            % (recorded,)
        )
        assert field(recorded, "overall") == "fail"

        # Every criterion, with every detail field, verbatim and untruncated.
        recorded_criteria = field(recorded, "criteria")
        assert len(recorded_criteria) == len(expected_report["criteria"])
        for got, want in zip(recorded_criteria, expected_report["criteria"]):
            assert got == want

        assert field(recorded, "requirement_results") == expected_report["requirement_results"]
        assert field(recorded, "interface_drift") is True
        assert field(recorded, "mutation_score") == expected_report["mutation_score"]
        assert field(recorded, "component_id") == COMPONENT_ID

        # And the whole thing is exactly the report handed in: nothing
        # summarized, truncated, dropped or added.
        assert recorded == expected_report