# hotdocs-criterion: sha256:53bb38e13bcc78c428a875770d234fae51ac43d752fe64ff1374338718acdf10
import copy
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _failing_report():
    criteria = []
    requirement_results = {}
    for i in range(1, 61):
        cid = "AC-FOO-" + str(i).zfill(3)
        rid = "R-FOO-" + str(i).zfill(3)
        if i % 3 == 0:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "generated-test",
                "result": "fail",
                "test_authoring": {
                    "model": "gpt-5",
                    "seed": i,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
                "failure_origin": "implementation",
                "failure_detail": {
                    "message": "assertion failed for " + cid + ": " + ("x" * 5000),
                    "expected": {"nested": [1, 2, {"deep": "value-" + str(i)}]},
                    "actual": [i, None, True, "actual-" + str(i)],
                },
            }
            requirement_results[rid] = "fail"
        elif i % 3 == 1:
            entry = {"id": cid, "covers": rid, "kind": "compiled", "result": "pass"}
            requirement_results[rid] = "pass"
        else:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            }
            requirement_results[rid] = "skipped"
        criteria.append(entry)

    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": True,
        "mutation_score": 0.42,
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
            "spec_bundle_hash": "sha256:" + ("e" * 64),
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
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def test_failing_verification_report_is_written_in_full(tmp_path):
    report = _failing_report()
    expected = copy.deepcopy(report)

    provenance_writer.write_provenance("comp-foo", _inputs(report), Path(tmp_path))

    paths = [
        tmp_path / "gen" / "foo" / ".provenance.json",
        tmp_path / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        written = field(manifest, "verification_report")
        assert isinstance(written, dict)
        assert written["overall"] == "fail"
        assert len(written["criteria"]) == len(expected["criteria"])
        for got, want in zip(written["criteria"], expected["criteria"]):
            assert got == want
        assert written == expected