# hotdocs-criterion: sha256:b141ffcfabfa1d5f9134f714edf79d00cdadb26c429c48cde7a6a81b9d70b17c
"""AC-PROV-005: a failing VerificationReport is written into the manifest in full.

Covers: R-PROV-005
"""

import copy
import dataclasses
import json

import pytest

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _build_failing_report():
    criteria = []
    requirement_results = {}
    for i in range(1, 41):
        cid = "AC-FOO-" + str(i).zfill(3)
        rid = "R-FOO-" + str(i).zfill(3)
        if i % 4 == 0:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {
                    "message": "result.value equals " + str(i) + " failed " + ("x" * 300),
                    "expected": i,
                    "actual": i - 1,
                },
                "failure_origin": "implementation",
            }
            requirement_results[rid] = "fail"
        elif i % 4 == 1:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "generated-test",
                "result": "pass",
                "test_authoring": {
                    "model": "gpt-5",
                    "seed": i,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
            }
            requirement_results[rid] = "pass"
        elif i % 4 == 2:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            }
            requirement_results[rid] = "skipped"
        else:
            entry = {
                "id": cid,
                "covers": rid,
                "kind": "generated-test",
                "result": "fail",
                "failure_detail": {
                    "message": "assertion failed in test " + str(i),
                    "expected": [1, 2, 3],
                    "actual": {"nested": [i, None, True]},
                },
                "failure_origin": "test",
            }
            requirement_results[rid] = "fail"
        criteria.append(entry)

    return {
        "component_id": COMPONENT_ID,
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
        "drivers": [],
        "overall": "fail",
    }


@dataclasses.dataclass
class _Report:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    mutation_error: object
    assets: list
    drivers: list
    overall: str

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "criteria": copy.deepcopy(self.criteria),
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "mutation_error": self.mutation_error,
            "assets": copy.deepcopy(self.assets),
            "drivers": copy.deepcopy(self.drivers),
            "overall": self.overall,
        }


def _inputs(report):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
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


def _read_manifests(repo_root):
    paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    manifests = []
    for p in paths:
        assert p.is_file(), "manifest not written at " + str(p)
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    return manifests


@pytest.mark.parametrize("shape", ["dict", "dataclass"])
def test_failing_report_written_in_full(tmp_path, shape):
    expected = _build_failing_report()
    if shape == "dict":
        report = copy.deepcopy(expected)
    else:
        report = _Report(**copy.deepcopy(expected))

    assert field(report, "overall") == "fail"

    provenance_writer.write_provenance(COMPONENT_ID, _inputs(report), tmp_path)

    for manifest in _read_manifests(tmp_path):
        written = manifest["verification_report"]
        assert isinstance(written, dict)
        # The full report, not a summary: every key and every value kept.
        assert written == expected
        assert written["overall"] == "fail"
        assert len(written["criteria"]) == len(expected["criteria"])
        for got, want in zip(written["criteria"], expected["criteria"]):
            assert got == want
        assert written["requirement_results"] == expected["requirement_results"]
        # Long failure messages are not truncated.
        assert written["criteria"][3]["failure_detail"]["message"] == \
            expected["criteria"][3]["failure_detail"]["message"]