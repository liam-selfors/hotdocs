"""AC-PROV-005 (Covers: R-PROV-005).

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


def _failing_report():
    """A rich, deliberately large VerificationReport whose overall is fail.

    It carries every optional detail a summary or truncation would drop:
    failure_detail, rationale, test_authoring, requirement_results,
    interface_drift, mutation_score, and many criteria with long text.
    """
    long_rationale = (
        "The judged behavior diverges from the requirement in several ways. "
        * 80
    ).strip()
    long_message = "widget.count equals 5 failed; " * 60

    criteria = [
        {
            "id": "AC-WIDGET-MAKER-001",
            "covers": "R-WIDGET-MAKER-001",
            "kind": "compiled",
            "result": "pass",
        },
        {
            "id": "AC-WIDGET-MAKER-002",
            "covers": "R-WIDGET-MAKER-002",
            "kind": "compiled",
            "result": "fail",
            "failure_detail": {
                "message": long_message,
                "expected": 5,
                "actual": 3,
            },
        },
        {
            "id": "AC-WIDGET-MAKER-003",
            "covers": "R-WIDGET-MAKER-003",
            "kind": "llm-judge",
            "result": "fail",
            "rationale": long_rationale,
        },
        {
            "id": "AC-WIDGET-MAKER-004",
            "covers": "R-WIDGET-MAKER-004",
            "kind": "llm-judge",
            "result": "skipped",
            "rationale": None,
        },
        {
            "id": "AC-WIDGET-MAKER-005",
            "covers": "R-WIDGET-MAKER-005",
            "kind": "generated-test",
            "result": "fail",
            "test_authoring": {
                "model": "anthropic:claude-sonnet-5",
                "seed": 0,
                "prompt_version": "v1",
                "cache_hit": False,
            },
            "failure_detail": {
                "message": "assert make_widget(2) == {'size': 2} failed",
                "expected": {"size": 2, "tags": ["a", "b"]},
                "actual": {"size": 1, "tags": []},
            },
        },
    ]
    # Many more criteria so that any truncation of the list is detectable.
    for n in range(6, 46):
        criteria.append(
            {
                "id": "AC-WIDGET-MAKER-%03d" % n,
                "covers": "R-WIDGET-MAKER-%03d" % n,
                "kind": "compiled",
                "result": "pass" if n % 3 else "fail",
                **(
                    {}
                    if n % 3
                    else {
                        "failure_detail": {
                            "message": "check %d failed" % n,
                            "expected": n,
                            "actual": n - 1,
                        }
                    }
                ),
            }
        )

    requirement_results = {
        c["covers"]: ("pass" if c["result"] == "pass" else "fail")
        for c in criteria
    }

    return {
        "component_id": COMPONENT_ID,
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": True,
        "mutation_score": 0.4375,
        "overall": "fail",
    }


def _inputs(report):
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget_maker.py": "def make_widget(n):\n    return {'size': n}\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-WIDGET-MAKER-002"],
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
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def test_ac_prov_005_failing_report_written_in_full(tmp_path):
    repo_root = Path(tmp_path)
    # The generated candidate exists on disk, as it would after generation.
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True)
    (gen_dir / "widget_maker.py").write_text(
        "def make_widget(n):\n    return {'size': n}\n", encoding="utf-8"
    )

    report = _failing_report()
    expected = json.loads(json.dumps(copy.deepcopy(report)))
    assert expected["overall"] == "fail"

    provenance_writer.write_provenance(COMPONENT_ID, _inputs(report), repo_root)

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    for path in manifest_paths:
        assert path.is_file(), "manifest not written at %s" % path
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert "verification_report" in manifest, path
        written = manifest["verification_report"]

        # The full report, not a summary: identical content, every key.
        assert isinstance(written, dict), path
        assert field(written, "overall") == "fail"
        assert written == expected, (
            "verification_report in %s is not the full report" % path
        )

        # Spot-check the details a summary or truncation would lose.
        assert len(written["criteria"]) == len(expected["criteria"])
        by_id = {c["id"]: c for c in written["criteria"]}
        assert (
            by_id["AC-WIDGET-MAKER-002"]["failure_detail"]
            == expected["criteria"][1]["failure_detail"]
        )
        assert (
            by_id["AC-WIDGET-MAKER-003"]["rationale"]
            == expected["criteria"][2]["rationale"]
        )
        assert (
            by_id["AC-WIDGET-MAKER-005"]["test_authoring"]
            == expected["criteria"][4]["test_authoring"]
        )
        assert written["requirement_results"] == expected["requirement_results"]
        assert written["interface_drift"] is True
        assert written["mutation_score"] == 0.4375