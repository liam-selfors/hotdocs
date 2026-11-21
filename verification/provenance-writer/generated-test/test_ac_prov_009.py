# hotdocs-criterion: sha256:672fdb5dc7e5cb3d601574b05b78e06cc7d03befc1a649340399633977e96966
"""AC-PROV-009: with provenance_hit true, the caller-sourced
verification_report / license_scan / secret_scan are written verbatim,
and write_provenance performs no lookup of its own."""

import copy
import json
import os
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-prov-hit-sample"
SLUG = "prov-hit-sample"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-PROV-HIT-SAMPLE-001", "covers": "R-PROV-HIT-SAMPLE-001",
             "kind": "compiled", "result": "pass"},
            {"id": "AC-PROV-HIT-SAMPLE-002", "covers": "R-PROV-HIT-SAMPLE-002",
             "kind": "generated-test", "result": "pass",
             "test_authoring": {"model": "prior-model-zeta", "seed": 7,
                                "prompt_version": "v-prior-41", "cache_hit": True}},
        ],
        "requirement_results": {"R-PROV-HIT-SAMPLE-001": "pass",
                                "R-PROV-HIT-SAMPLE-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.8125,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "ab" * 32,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "overall": "pass",
        "prior_manifest_marker": "sourced-by-caller-from-prior-manifest",
    }


def _license_scan():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.9+0123456789ab",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.3125,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [{"reference_id": "ref-prior-77", "license_family": "mit",
                     "risk_tier": "low", "score": 0.3125}],
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
        "allowed": [{"rule_id": "Prior Rule", "file": "verification/x/test_y.py", "line": 4}],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _write_fake(repo_root, slug, module_name, body):
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import os\n"
        "def _log(what):\n"
        "    with open(os.environ['PROV009_LOG'], 'a') as fh:\n"
        "        fh.write(" + repr(module_name + ":") + " + what + '\\n')\n"
        "_log('import')\n"
        + body
    )
    (d / (module_name + ".py")).write_text(src)


CACHE_MANAGER_BODY = (
    "from dataclasses import dataclass\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get')\n"
    "    return Miss()\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put')\n"
    "    return None\n"
    "def now_iso():\n"
    "    _log('now_iso')\n"
    "    return '2026-01-01T00:00:00Z'\n"
    "def stats(*, repo_root=None):\n"
    "    _log('stats')\n"
    "    return {'entry_count': 0}\n"
)


def test_provenance_hit_fields_written_verbatim_without_lookup(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "lookup.log"
    log_path.write_text("")
    monkeypatch.setenv("PROV009_LOG", str(log_path))

    # Fakes that would record any attempt by the writer to look something up.
    _write_fake(repo_root, "cache-manager", "cache_manager", CACHE_MANAGER_BODY)
    _write_fake(repo_root, "provenance-checker", "provenance_checker", "")

    # A decoy prior manifest holding different values: never to be consulted.
    decoy = {"verification_report": {"overall": "fail", "decoy": True},
             "license_scan": {"decoy": True}, "secret_scan": {"decoy": True},
             "provenance_hit": False}
    for top in ("gen", "verification"):
        d = repo_root / top / SLUG
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(json.dumps(decoy))

    report = _verification_report()
    lic = _license_scan()
    sec = _secret_scan()
    expected_report = copy.deepcopy(report)
    expected_lic = copy.deepcopy(lic)
    expected_sec = copy.deepcopy(sec)

    inputs = {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": "sha256:" + "cd" * 32,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": True,
            "files": {"prov_hit_sample.py": "X = 1\n"},
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
        "license_scan_result": lic,
        "secret_scan_result": sec,
        "provenance_hit": True,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {"compiler": "1.0.0"},
    }

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    for top in ("gen", "verification"):
        path = repo_root / top / SLUG / ".provenance.json"
        assert path.is_file(), path
        manifest = json.loads(path.read_text())
        assert field(manifest, "provenance_hit") is True
        assert field(manifest, "verification_report") == expected_report
        assert field(manifest, "license_scan") == expected_lic
        assert field(manifest, "secret_scan") == expected_sec

    gen_bytes = (repo_root / "gen" / SLUG / ".provenance.json").read_bytes()
    ver_bytes = (repo_root / "verification" / SLUG / ".provenance.json").read_bytes()
    assert gen_bytes == ver_bytes

    # The caller's inputs were not altered either.
    assert report == expected_report
    assert lic == expected_lic
    assert sec == expected_sec

    # No lookup: neither fake dependency was loaded or called.
    assert log_path.read_text() == "", log_path.read_text()