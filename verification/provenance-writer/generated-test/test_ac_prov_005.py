# hotdocs-criterion: sha256:ad37e72a06e869935551e835a7e2a274640729b1961d1ceee0c41822f0d6fd1e
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _full_failing_report():
    criteria = []
    requirement_results = {}
    for i in range(1, 41):
        rid = "R-FOO-" + str(i).zfill(3)
        cid = "AC-FOO-" + str(i).zfill(3)
        if i % 4 == 0:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {
                    "message": "result.value equals " + str(i) + " failed; "
                    + ("long diagnostic text " * 30).strip(),
                    "expected": i,
                    "actual": {"nested": [i, i + 1, {"deep": "x" * 200}]},
                },
                "failure_origin": "implementation",
            }
            requirement_results[rid] = "fail"
        elif i % 4 == 1:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            }
            requirement_results[rid] = "fail"
        elif i % 4 == 2:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "generated-test",
                "result": "fail",
                "test_authoring": {
                    "model": "gpt-5",
                    "seed": 0,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
                "failure_detail": {
                    "message": "assertion failed in generated test " + cid,
                    "expected": [1, 2, 3],
                    "actual": None,
                },
                "failure_origin": "test",
            }
            requirement_results[rid] = "fail"
        else:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "compiled",
                "result": "pass",
            }
            requirement_results[rid] = "pass"
        criteria.append(entry)
    return {
        "component_id": COMPONENT_ID,
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": True,
        "mutation_score": 0.37,
        "mutation_error": None,
        "overall": "fail",
    }


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "def f():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
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


def _make_inputs(report):
    data = {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": report,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and isinstance(cls, type):
        try:
            return cls(**data)
        except Exception:
            pass
    return data


def test_failing_verification_report_is_recorded_in_full(tmp_path):
    repo_root = tmp_path
    (repo_root / "gen" / SLUG).mkdir(parents=True)
    (repo_root / "gen" / SLUG / "foo.py").write_text("def f():\n    return 1\n")
    (repo_root / "verification" / SLUG).mkdir(parents=True)

    report = _full_failing_report()
    expected = json.loads(json.dumps(report))

    provenance_writer.write_provenance(COMPONENT_ID, _make_inputs(report), repo_root)

    paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        recorded = field(manifest, "verification_report")
        assert isinstance(recorded, dict)
        assert field(recorded, "overall") == "fail"
        assert len(field(recorded, "criteria")) == len(expected["criteria"])
        assert recorded == expected