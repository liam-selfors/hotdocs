# hotdocs-criterion: sha256:637de8e71f451a75563521d9712f98324efa35363d2803233bd37a0b93e7b906
"""AC-PROV-009: with provenance_hit true, write_provenance writes the
verification_report / license_scan / secret_scan its ProvenanceInputs
carries verbatim, unchanged, and performs no lookup of its own."""

import copy
import json
import os
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fake_cache_manager(repo_root: Path, log_path: Path) -> None:
    """A fake cache-manager matching its documented interface; every
    function call appends one line to a log file the test controls."""
    base = repo_root / "gen" / "cache-manager"
    base.mkdir(parents=True, exist_ok=True)
    src = (
        "import os\n"
        "from dataclasses import dataclass\n"
        "\n"
        "_LOG_ENV = " + repr("AC_PROV_009_LOG") + "\n"
        "\n"
        "def _log(name):\n"
        "    p = os.environ.get(_LOG_ENV)\n"
        "    if p:\n"
        "        with open(p, " + repr("a") + ") as fh:\n"
        "            fh.write(name + " + repr("\n") + ")\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log(" + repr("get") + ")\n"
        "    return Miss()\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log(" + repr("put") + ")\n"
        "    return None\n"
        "\n"
        "def now_iso():\n"
        "    _log(" + repr("now_iso") + ")\n"
        "    return " + repr("2026-01-01T00:00:00Z") + "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    _log(" + repr("stats") + ")\n"
        "    return {" + repr("entry_count") + ": 0}\n"
    )
    (base / "cache_manager.py").write_text(src, encoding="utf-8")


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge",
             "result": "skipped", "rationale": None},
            {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "generated-test",
             "result": "pass",
             "test_authoring": {"model": "prior-model-marker", "seed": 7,
                                "prompt_version": "v-prior", "cache_hit": True}},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail",
                                "R-FOO-003": "pass"},
        "interface_drift": False,
        "mutation_score": 0.8125,
        "mutation_error": None,
        "overall": "pass",
    }


def _license_scan():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.3125,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [
            {"reference_id": "ref-prior-marker", "license_family": "gpl-3.0",
             "risk_tier": "medium", "score": 0.3125}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [
            {"rule_id": "AWS Access Key", "file": "verification/foo/test_prior.py",
             "line": 3}
        ],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": True,
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _different_prior_manifest():
    return {
        "spec_bundle_hash": "sha256:" + "cd" * 32,
        "model_pin": "other-model",
        "prompt_version": "v0",
        "retry_feedback": None,
        "pipeline_version": "v0",
        "gate_versions": {},
        "provenance_hit": False,
        "generated_at": "2020-01-01T00:00:00Z",
        "verification_run_id": "run-stale",
        "verification_report": {"component_id": COMPONENT_ID, "overall": "fail",
                                "criteria": [], "stale_marker": True},
        "license_scan": {"stale_marker": True},
        "secret_scan": {"stale_marker": True},
    }


def test_provenance_hit_fields_written_verbatim_without_lookup(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "lookup.log"
    monkeypatch.setenv("AC_PROV_009_LOG", str(log_path))

    _write_fake_cache_manager(repo_root, log_path)

    # Stale, different manifests already sit at both locations: if the
    # component looked anything up itself, these would be its source.
    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"
    for p in (gen_manifest, ver_manifest):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_different_prior_manifest()), encoding="utf-8")

    report = _verification_report()
    license_scan = _license_scan()
    secret_scan = _secret_scan()

    inputs = {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": report,
        "license_scan_result": license_scan,
        "secret_scan_result": secret_scan,
        "provenance_hit": True,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0",
                          "license_scanner": "license_scanner@4.0.3+9f2c41ab07de"},
    }

    expected_report = copy.deepcopy(report)
    expected_license = copy.deepcopy(license_scan)
    expected_secret = copy.deepcopy(secret_scan)

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    for p in (gen_manifest, ver_manifest):
        assert p.is_file(), "manifest missing at " + str(p)
        manifest = json.loads(p.read_text(encoding="utf-8"))
        assert field(manifest, "provenance_hit") is True
        assert field(manifest, "verification_report") == expected_report
        assert field(manifest, "license_scan") == expected_license
        assert field(manifest, "secret_scan") == expected_secret

    # The inputs themselves were not mutated.
    assert report == expected_report
    assert license_scan == expected_license
    assert secret_scan == expected_secret

    # No lookup performed by this component itself.
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert "get" not in calls, "write_provenance performed a cache lookup: " + repr(calls)
    assert calls == [] or set(calls) <= {"now_iso"}, (
        "write_provenance called cache-manager: " + repr(calls)
    )