# hotdocs-criterion: sha256:5174209acdd81097ec29f8799d694ae3022edf9324e7009875b12512fe43732f
"""AC-PROV-009: with provenance_hit true, write_provenance writes the
verification_report / license_scan / secret_scan it is handed verbatim,
performing no lookup of its own (R-PROV-009)."""

import copy
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-prov-hit-demo"
SLUG = "prov-hit-demo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _carried_verification_report():
    # As if sourced by the caller from a matching prior manifest.
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-PROV-HIT-DEMO-001", "covers": "R-PROV-HIT-DEMO-001",
             "kind": "compiled", "result": "pass"},
            {"id": "AC-PROV-HIT-DEMO-002", "covers": "R-PROV-HIT-DEMO-002",
             "kind": "llm-judge", "result": "skipped", "rationale": None},
            {"id": "AC-PROV-HIT-DEMO-003", "covers": "R-PROV-HIT-DEMO-003",
             "kind": "generated-test", "result": "pass",
             "test_authoring": {"model": "prior-model-marker", "seed": 7,
                                "prompt_version": "v-prior", "cache_hit": True}},
        ],
        "requirement_results": {
            "R-PROV-HIT-DEMO-001": "pass",
            "R-PROV-HIT-DEMO-002": "skipped",
            "R-PROV-HIT-DEMO-003": "pass",
        },
        "interface_drift": False,
        "mutation_score": 0.8125,
        "mutation_error": None,
        "assets": [
            {"kind": "python", "path": ".", "definition_sha256": None,
             "adapter_sha256": "sha256:" + "ab" * 32,
             "versions": {"python": "3.12.4"}, "lockfile_sha256": None},
        ],
        "drivers": [],
        "overall": "pass",
        "prior_manifest_marker": "carried-from-prior-run-42",
    }


def _carried_license_scan():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.9+0123456789ab",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.375,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [
            {"reference_id": "ref-prior-777", "license_family": "gpl-3.0",
             "risk_tier": "medium", "score": 0.375},
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _carried_secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [
            {"rule_id": "AWS Access Key", "file": "verification/prov-hit-demo/test_prior.py",
             "line": 11},
        ],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _inputs():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": "sha256:" + "cd" * 32,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": True,
            "files": {"prov_hit_demo.py": "X = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": _carried_verification_report(),
        "license_scan_result": _carried_license_scan(),
        "secret_scan_result": _carried_secret_scan(),
        "provenance_hit": True,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
        "spec_bundle_parts": {"spec": "sha256:" + "11" * 32,
                              "dependency_code": "sha256:" + "22" * 32},
    }


def _different_prior_manifest():
    # A decoy prior manifest already sitting where this component writes; a
    # component that looked anything up itself might pick these up instead.
    return {
        "provenance_hit": False,
        "verification_report": {"overall": "fail", "decoy": "prior-on-disk"},
        "license_scan": {"decoy": "prior-on-disk", "blocked": True},
        "secret_scan": {"decoy": "prior-on-disk", "flagged": True},
    }


def test_provenance_hit_fields_written_verbatim_without_lookup(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Fake provenance-checker that logs if it is ever loaded.
    log_path = tmp_path / "provenance_checker_calls.log"
    fake_dir = repo_root / "gen" / "provenance-checker"
    fake_dir.mkdir(parents=True)
    fake_src = (
        "from pathlib import Path\n"
        "with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as _f:\n"
        "    _f.write('imported\\n')\n"
    )
    (fake_dir / "provenance_checker.py").write_text(fake_src, encoding="utf-8")

    # Decoy prior manifests at the output locations.
    for sub in ("gen", "verification"):
        d = repo_root / sub / SLUG
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(
            json.dumps(_different_prior_manifest()), encoding="utf-8"
        )

    inputs = _inputs()
    snapshot = copy.deepcopy(inputs)

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    gen_path = repo_root / "gen" / SLUG / ".provenance.json"
    ver_path = repo_root / "verification" / SLUG / ".provenance.json"
    assert gen_path.is_file()
    assert ver_path.is_file()
    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()
    assert gen_bytes == ver_bytes

    for raw in (gen_bytes, ver_bytes):
        manifest = json.loads(raw.decode("utf-8"))
        assert field(manifest, "provenance_hit") is True
        assert field(manifest, "verification_report") == _carried_verification_report()
        assert field(manifest, "license_scan") == _carried_license_scan()
        assert field(manifest, "secret_scan") == _carried_secret_scan()

    # The inputs handed in were not altered either.
    assert inputs == snapshot

    # No lookup via provenance-checker was performed by this component.
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""