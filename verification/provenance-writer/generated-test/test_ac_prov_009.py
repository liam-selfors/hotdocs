"""AC-PROV-009 (Covers: R-PROV-009).

Given ProvenanceInputs with provenance_hit true, carrying
verification_report/license_scan/secret_scan already sourced from a prior
manifest by the caller, when write_provenance runs, then those three fields
are written verbatim, unchanged, with no lookup performed by this component
itself.
"""

import copy
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-prov-nine-widget"
SLUG = "prov-nine-widget"
LOG_ENV = "PROV009_INVOCATION_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Fake dependencies: any lookup through them is recorded to a file log.
# ---------------------------------------------------------------------------

FAKE_CACHE_MANAGER = '''
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone


def _log(name):
    path = os.environ.get("PROV009_INVOCATION_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"module": "cache_manager", "name": name}) + "\\n")


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


def get(cache_key, *, repo_root=None):
    _log("get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _log("put")
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    _log("stats")
    return {"entry_count": 0}
'''

FAKE_PROVENANCE_CHECKER = '''
import json
import os


def _log(name):
    path = os.environ.get("PROV009_INVOCATION_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"module": "provenance_checker", "name": name}) + "\\n")


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)

    def _called(*args, **kwargs):
        _log(name)
        return None

    return _called
'''


def _plant_fakes(repo_root: Path):
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    pc_dir = repo_root / "gen" / "provenance-checker"
    pc_dir.mkdir(parents=True, exist_ok=True)
    (pc_dir / "provenance_checker.py").write_text(
        FAKE_PROVENANCE_CHECKER, encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Inputs: distinctive values "sourced from a prior manifest" by the caller.
# ---------------------------------------------------------------------------

def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-PROV-NINE-WIDGET-001",
                "covers": "R-PROV-NINE-WIDGET-001",
                "kind": "compiled",
                "result": "pass",
            },
            {
                "id": "AC-PROV-NINE-WIDGET-002",
                "covers": "R-PROV-NINE-WIDGET-002",
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            },
            {
                "id": "AC-PROV-NINE-WIDGET-003",
                "covers": "R-PROV-NINE-WIDGET-003",
                "kind": "generated-test",
                "result": "pass",
                "test_authoring": {
                    "model": "prior-manifest-author-model",
                    "seed": 7,
                    "prompt_version": "v-prior-77",
                    "cache_hit": True,
                },
            },
        ],
        "requirement_results": {
            "R-PROV-NINE-WIDGET-001": "pass",
            "R-PROV-NINE-WIDGET-002": "fail",
            "R-PROV-NINE-WIDGET-003": "pass",
        },
        "interface_drift": False,
        "mutation_score": 0.8125,
        "overall": "pass",
    }


def _license_scan():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.9+abcdefabcdef",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.3125,
        "block_threshold": 0.65,
        "blocked": False,
        "matches": [
            {
                "reference_id": "ref-prior-0909",
                "license_family": "mpl-2.0",
                "risk_tier": "medium",
                "score": 0.3125,
            }
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
            {
                "rule_id": "Base64 High Entropy String",
                "file": "verification/prov-nine-widget/test_prior.py",
                "line": 9,
            }
        ],
        "unused_allowlist_entries": [
            {"file": "verification/prov-nine-widget/old.py", "type": "Hex High Entropy String"}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "9" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": True,
        "files": {"prov_nine_widget.py": "def widget_value():\n    return 9\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _inputs():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan(),
        "secret_scan_result": _secret_scan(),
        "provenance_hit": True,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.9+abcdefabcdef",
        },
    }


def _decoy_manifest():
    """A different prior manifest sitting on disk: must not be consulted."""
    return {
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model_pin": "decoy-model",
        "prompt_version": "v0",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": {"compiler": "0.0.1"},
        "provenance_hit": False,
        "generated_at": "2000-01-01T00:00:00Z",
        "verification_run_id": "run-decoy",
        "verification_report": {
            "component_id": COMPONENT_ID,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": True,
            "mutation_score": 0.0,
            "overall": "fail",
        },
        "license_scan": {"component_id": COMPONENT_ID, "decoy": True},
        "secret_scan": {"scope": "full", "decoy": True},
    }


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(value):
    """JSON round-trip so tuples/lists and similar compare as written."""
    return json.loads(json.dumps(value))


def test_ac_prov_009_hit_fields_written_verbatim_without_lookup(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.chdir(repo_root)

    _plant_fakes(repo_root)

    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"
    for path in (gen_manifest, ver_manifest):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_decoy_manifest(), indent=2), encoding="utf-8")

    inputs = _inputs()
    inputs_before = copy.deepcopy(inputs)

    expected_report = _normalize(_verification_report())
    expected_license = _normalize(_license_scan())
    expected_secret = _normalize(_secret_scan())

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    # The caller's inputs are not altered.
    assert inputs == inputs_before

    for path in (gen_manifest, ver_manifest):
        assert path.is_file(), f"manifest missing at {path}"
        manifest = _read_json(path)
        assert field(manifest, "provenance_hit") is True
        assert field(manifest, "verification_report") == expected_report, path
        assert field(manifest, "license_scan") == expected_license, path
        assert field(manifest, "secret_scan") == expected_secret, path

    # No lookup was performed through any dependency.
    calls = []
    if log_path.exists():
        calls = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    assert calls == [], f"write_provenance performed lookups itself: {calls}"