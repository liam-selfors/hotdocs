# hotdocs-criterion: sha256:cdbdc64259ad1573ce811a2bcc4ac204d117fea9ff33c8de8997f1334d95df42
import dataclasses
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            },
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
        "mutation_error": None,
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


def _inputs():
    data = {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
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
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            return data
    return data


def test_ac_prov_010_both_manifest_copies_are_byte_identical(tmp_path):
    repo_root = Path(tmp_path)
    (repo_root / "gen" / SLUG).mkdir(parents=True, exist_ok=True)
    (repo_root / "verification" / SLUG).mkdir(parents=True, exist_ok=True)

    provenance_writer.write_provenance(COMPONENT_ID, _inputs(), repo_root)

    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"

    assert gen_manifest.is_file(), "gen/<component>/.provenance.json was not written"
    assert ver_manifest.is_file(), "verification/<component>/.provenance.json was not written"

    gen_bytes = gen_manifest.read_bytes()
    ver_bytes = ver_manifest.read_bytes()

    assert len(gen_bytes) > 0
    # Sanity: it is a real JSON manifest, not an empty placeholder.
    assert isinstance(json.loads(gen_bytes.decode("utf-8")), dict)

    assert gen_bytes == ver_bytes, "the two provenance manifest copies diverge"