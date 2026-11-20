# hotdocs-criterion: sha256:a1fc4bf2a0af22f02a5592aebd077007bb97fee5496fbbf31c80d488a6dbcf32
import copy
import json
import os

import pytest

import provenance_writer


SLUG = "widget-maker"
COMPONENT_ID = "comp-" + SLUG
LOG_ENV = "HOTDOCS_TEST_PROV009_LOOKUP_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_module_source(label):
    # Built by concatenation with repr() for embedded values; no temp paths embedded.
    return (
        "import os\n"
        "\n"
        "def _log(what):\n"
        "    path = os.environ.get(" + repr(LOG_ENV) + ")\n"
        "    if path:\n"
        "        with open(path, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(" + repr(label) + " + ':' + what + '\\n')\n"
        "\n"
        "_log('import')\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get')\n"
        "    return {'gate_type': 'generator', 'payload': {'decoy': True},\n"
        "            'stored_at': '2020-01-01T00:00:00Z'}\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put')\n"
        "    return None\n"
        "\n"
        "def check(*args, **kwargs):\n"
        "    _log('check')\n"
        "    return {'hit': True, 'manifest': {'verification_report': {'decoy': True},\n"
        "            'license_scan': {'decoy': True}, 'secret_scan': {'decoy': True}}}\n"
        "\n"
        "def lookup(*args, **kwargs):\n"
        "    _log('lookup')\n"
        "    return check(*args, **kwargs)\n"
        "\n"
        "def find_prior_manifest(*args, **kwargs):\n"
        "    _log('find_prior_manifest')\n"
        "    return check(*args, **kwargs)\n"
    )


def _sourced_verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-WIDGET-MAKER-001", "covers": "R-WIDGET-MAKER-001",
             "kind": "compiled", "result": "pass"},
            {"id": "AC-WIDGET-MAKER-002", "covers": "R-WIDGET-MAKER-002",
             "kind": "llm-judge", "result": "skipped", "rationale": None},
            {"id": "AC-WIDGET-MAKER-003", "covers": "R-WIDGET-MAKER-003",
             "kind": "generated-test", "result": "pass",
             "test_authoring": {"model": "prior-model-x", "seed": 7,
                                "prompt_version": "v9", "cache_hit": True}},
        ],
        "requirement_results": {
            "R-WIDGET-MAKER-001": "pass",
            "R-WIDGET-MAKER-002": "skipped",
            "R-WIDGET-MAKER-003": "pass",
        },
        "interface_drift": False,
        "mutation_score": 0.875,
        "mutation_error": None,
        "assets": [
            {"kind": "python", "path": ".", "definition_sha256": None,
             "adapter_sha256": "sha256:" + "ab" * 32,
             "versions": {"python": "3.12.4"}, "lockfile_sha256": None},
        ],
        "overall": "pass",
        "prior_manifest_marker": "sourced-from-prior-manifest-run-41",
    }


def _sourced_license_scan():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.125,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [
            {"reference_id": "ref-prior-77", "license_family": "mit",
             "risk_tier": "low", "score": 0.125},
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _sourced_secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [
            {"rule_id": "AWS Access Key",
             "file": "verification/widget-maker/test_x.py", "line": 3},
        ],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _inputs(report, lic, sec):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": "sha256:" + "cd" * 32,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": True,
            "files": {"widget_maker.py": "VALUE = 1\n"},
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
        "gate_versions": {"compiler": "1.0.0",
                          "license_scanner": "k-gram@1.0.0"},
    }


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "lookup.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    for slug, label in (("cache-manager", "cache_manager"),
                        ("provenance-checker", "provenance_checker")):
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(
            _fake_module_source(label), encoding="utf-8")
    return repo_root, log_path


def test_provenance_hit_fields_written_verbatim_without_lookup(repo):
    repo_root, log_path = repo

    report = _sourced_verification_report()
    lic = _sourced_license_scan()
    sec = _sourced_secret_scan()
    expected_report = copy.deepcopy(report)
    expected_lic = copy.deepcopy(lic)
    expected_sec = copy.deepcopy(sec)

    inputs = _inputs(report, lic, sec)

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"
    assert gen_manifest.is_file()
    assert ver_manifest.is_file()
    assert gen_manifest.read_bytes() == ver_manifest.read_bytes()

    for manifest_path in (gen_manifest, ver_manifest):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert field(manifest, "provenance_hit") is True
        assert field(manifest, "verification_report") == expected_report
        assert field(manifest, "license_scan") == expected_lic
        assert field(manifest, "secret_scan") == expected_sec
        assert field(manifest, "assets") == expected_report["assets"]

    # The inputs themselves were left unchanged.
    assert report == expected_report
    assert lic == expected_lic
    assert sec == expected_sec

    # No lookup was performed by this component: neither decoy dependency
    # was loaded or called.
    if log_path.exists():
        logged = log_path.read_text(encoding="utf-8")
    else:
        logged = ""
    assert logged == "", "write_provenance performed a lookup: " + repr(logged)


def test_provenance_hit_does_not_replace_fields_from_existing_manifest(repo):
    repo_root, log_path = repo

    # A prior manifest already sits at the target location with different
    # values; the writer must not source anything from it.
    decoy = {
        "provenance_hit": False,
        "verification_report": {"decoy": "prior-report"},
        "license_scan": {"decoy": "prior-license"},
        "secret_scan": {"decoy": "prior-secret"},
    }
    for sub in ("gen", "verification"):
        d = repo_root / sub / SLUG
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(json.dumps(decoy), encoding="utf-8")

    report = _sourced_verification_report()
    lic = _sourced_license_scan()
    sec = _sourced_secret_scan()
    expected_report = copy.deepcopy(report)
    expected_lic = copy.deepcopy(lic)
    expected_sec = copy.deepcopy(sec)

    provenance_writer.write_provenance(
        COMPONENT_ID, _inputs(report, lic, sec), repo_root)

    for sub in ("gen", "verification"):
        path = repo_root / sub / SLUG / ".provenance.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert field(manifest, "provenance_hit") is True
        assert field(manifest, "verification_report") == expected_report
        assert field(manifest, "license_scan") == expected_lic
        assert field(manifest, "secret_scan") == expected_sec

    logged = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert logged == "", "write_provenance performed a lookup: " + repr(logged)