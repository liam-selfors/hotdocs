# hotdocs-criterion: sha256:b80c17340c66f54b75e3cc7e95f04ac2f53db772930f6fb3828025d475092988
import copy
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _failing_report():
    long_message = "assertion failed: " + ("x" * 5000) + " END-OF-MESSAGE"
    criteria = []
    requirement_results = {}
    for i in range(1, 41):
        rid = "R-FOO-%03d" % i
        cid = "AC-FOO-%03d" % i
        if i % 4 == 0:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "generated-test",
                "result": "fail",
                "failure_origin": "implementation",
                "failure_detail": {
                    "message": long_message + " #" + str(i),
                    "expected": {"values": list(range(i)), "nested": {"k": [1, 2, {"deep": "yes"}]}},
                    "actual": {"values": list(range(i - 1)), "nested": {"k": [1, 2, {"deep": "no"}]}},
                },
                "test_authoring": {
                    "model": "gpt-5",
                    "seed": i,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
            }
            requirement_results[rid] = "fail"
        elif i % 7 == 0:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            }
            requirement_results[rid] = "skipped"
        else:
            entry = {"id": cid, "covers": rid, "kind": "compiled", "result": "pass"}
            requirement_results[rid] = "pass"
        criteria.append(entry)
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": False,
        "mutation_score": 0.4375,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + ("a" * 64),
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            },
            {
                "kind": "javascript",
                "path": "static/app.js",
                "definition_sha256": "sha256:" + ("b" * 64),
                "adapter_sha256": "sha256:" + ("c" * 64),
                "versions": {"node": "24.1.0"},
                "lockfile_sha256": "sha256:" + ("d" * 64),
            },
        ],
        "overall": "fail",
    }


def _inputs(report):
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + ("0" * 64),
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"foo.py": "def foo():\n    return 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": report,
        "license_scan_result": {
            "component_id": "comp-foo",
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
        },
        "secret_scan_result": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [
            {
                "number": 1,
                "outcome": "verification_failed",
                "retry_feedback": [],
                "error_category": None,
                "failed_requirements": ["R-FOO-004"],
                "transcript_sha256": None,
            }
        ],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def test_failing_verification_report_is_written_in_full(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report = _failing_report()
    expected = copy.deepcopy(report)

    provenance_writer.write_provenance("comp-foo", _inputs(report), repo_root)

    gen_path = repo_root / "gen" / "foo" / ".provenance.json"
    ver_path = repo_root / "verification" / "foo" / ".provenance.json"
    assert gen_path.is_file()
    assert ver_path.is_file()

    for path in (gen_path, ver_path):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        written = field(manifest, "verification_report")
        assert isinstance(written, dict)
        assert field(written, "overall") == "fail"
        # Every criterion entry, in order, with every key, untruncated.
        assert len(field(written, "criteria")) == len(expected["criteria"])
        assert field(written, "criteria") == expected["criteria"]
        assert field(written, "requirement_results") == expected["requirement_results"]
        for entry in field(written, "criteria"):
            if entry["result"] == "fail":
                assert entry["failure_detail"]["message"].startswith("assertion failed: ")
                assert "END-OF-MESSAGE" in entry["failure_detail"]["message"]
                assert len(entry["failure_detail"]["message"]) > 5000
        # The whole report, exactly: nothing dropped, summarized or truncated.
        assert written == expected