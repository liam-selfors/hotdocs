import copy
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-widget-assembler"
SLUG = "widget-assembler"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


_LOG_HELPER = '''
import json as _json
from pathlib import Path as _Path

_LOG = _Path(__file__).resolve().parents[2] / "invocations.log"


def _record(module, name, args=None, kwargs=None):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({"module": module, "name": name}) + "\\n")
'''


FAKE_CACHE_MANAGER = _LOG_HELPER + '''
from dataclasses import dataclass


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
    _record("cache_manager", "get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None


def now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}


def main(argv=None):
    return 0
'''


FAKE_VERIFIER = _LOG_HELPER + '''
GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _record("verifier_orchestrator", "verify")
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-LOOKED-UP-001", "covers": "R-LOOKED-UP-001",
             "kind": "compiled", "result": "fail"}
        ],
        "requirement_results": {"R-LOOKED-UP-001": "fail"},
        "interface_drift": True,
        "mutation_score": 0.01,
        "overall": "fail",
    }


def main(argv):
    return 0
'''


FAKE_LICENSE = _LOG_HELPER + '''
def scan(component_id, repo_root):
    _record("license_scanner", "scan")
    return {
        "component_id": component_id,
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


def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def main(argv):
    return 0
'''


FAKE_SECRET = _LOG_HELPER + '''
def _result(scope):
    return {
        "scope": scope,
        "gate_version": "secret_scanner@0.0.0+looked-up",
        "flagged": True,
        "matches": [{"rule_id": "Looked Up", "risk_tier": "high",
                     "file": "gen/x/y.py", "line": 1}],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def scan(repo_root):
    _record("secret_scanner", "scan")
    return _result("full")


def scan_files(paths, repo_root=None):
    _record("secret_scanner", "scan_files")
    return _result("precommit")


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


class AllowlistInvalidError(Exception):
    pass


def propose(repo_root):
    _record("secret_scanner", "propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}


def main(argv):
    return 0
'''


FAKE_GENERATOR = _LOG_HELPER + '''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _record("generator", "generate")
    return {
        "component_id": "comp-widget-assembler",
        "spec_bundle_hash": "sha256:" + "f" * 64,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": False,
        "files": {"looked_up.py": "x = 1\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
'''


FAKE_PROVENANCE_CHECKER = _LOG_HELPER + '''
def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)

    def _any(*args, **kwargs):
        _record("provenance_checker", name)
        return None

    return _any
'''


def _plant(repo_root: Path, slug: str, module_name: str, source: str) -> None:
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{module_name}.py").write_text(source, encoding="utf-8")


def _prior_manifest():
    return {
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model_pin": "prior-model",
        "prompt_version": "v0",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": {"compiler": "0.0.1"},
        "provenance_hit": False,
        "generated_at": "2020-01-01T00:00:00Z",
        "verification_run_id": "run-prior",
        "verification_report": {
            "component_id": COMPONENT_ID,
            "criteria": [{"id": "AC-PRIOR-001", "covers": "R-PRIOR-001",
                          "kind": "compiled", "result": "fail"}],
            "requirement_results": {"R-PRIOR-001": "fail"},
            "interface_drift": True,
            "mutation_score": 0.11,
            "overall": "fail",
        },
        "license_scan": {"component_id": COMPONENT_ID, "prior": True},
        "secret_scan": {"scope": "full", "prior": True},
    }


def _build_inputs_fields():
    verification_report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-WIDGET-ASSEMBLER-001", "covers": "R-WIDGET-ASSEMBLER-001",
             "kind": "compiled", "result": "pass"},
            {"id": "AC-WIDGET-ASSEMBLER-002", "covers": "R-WIDGET-ASSEMBLER-002",
             "kind": "llm-judge", "result": "skipped", "rationale": None},
            {"id": "AC-WIDGET-ASSEMBLER-003", "covers": "R-WIDGET-ASSEMBLER-003",
             "kind": "generated-test", "result": "pass",
             "test_authoring": {"model": "gpt-5", "seed": 7,
                                "prompt_version": "v3", "cache_hit": True}},
        ],
        "requirement_results": {
            "R-WIDGET-ASSEMBLER-001": "pass",
            "R-WIDGET-ASSEMBLER-002": "fail",
            "R-WIDGET-ASSEMBLER-003": "pass",
        },
        "interface_drift": False,
        "mutation_score": 0.875,
        "overall": "pass",
    }
    license_scan_result = {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.125,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [
            {"reference_id": "ref-777", "license_family": "mit",
             "risk_tier": "low", "score": 0.125}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }
    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [
            {"rule_id": "AWS Access Key",
             "file": "verification/widget-assembler/test_x.py", "line": 3}
        ],
        "unused_allowlist_entries": [
            {"file": "verification/widget-assembler/old.py",
             "type": "AWS Access Key"}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": True,
        "files": {"widget_assembler.py": "def assemble_widget(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": True,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        },
    }


def _make_inputs(fields):
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if isinstance(cls, type):
        try:
            return cls(**copy.deepcopy(fields))
        except TypeError:
            pass
    return copy.deepcopy(fields)


def test_ac_prov_009_hit_fields_written_verbatim_without_lookup(tmp_path):
    repo_root = tmp_path

    # Fake every dependency that could serve as a "lookup" source; each logs
    # any lookup-style call to a file the test controls.
    _plant(repo_root, "cache-manager", "cache_manager", FAKE_CACHE_MANAGER)
    _plant(repo_root, "verifier-orchestrator", "verifier_orchestrator", FAKE_VERIFIER)
    _plant(repo_root, "license-scanner", "license_scanner", FAKE_LICENSE)
    _plant(repo_root, "secret-scanner", "secret_scanner", FAKE_SECRET)
    _plant(repo_root, "generator", "generator", FAKE_GENERATOR)
    _plant(repo_root, "provenance-checker", "provenance_checker", FAKE_PROVENANCE_CHECKER)

    # A prior manifest with *different* values sits at both locations: if the
    # component looked anything up itself, these would leak into the output.
    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"
    for p in (gen_manifest, ver_manifest):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_prior_manifest()), encoding="utf-8")

    fields = _build_inputs_fields()
    expected_report = copy.deepcopy(fields["verification_report"])
    expected_license = copy.deepcopy(fields["license_scan_result"])
    expected_secret = copy.deepcopy(fields["secret_scan_result"])

    inputs = _make_inputs(fields)
    passed_report = copy.deepcopy(field(inputs, "verification_report"))
    passed_license = copy.deepcopy(field(inputs, "license_scan_result"))
    passed_secret = copy.deepcopy(field(inputs, "secret_scan_result"))

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    for manifest_path in (gen_manifest, ver_manifest):
        assert manifest_path.is_file(), f"manifest missing at {manifest_path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["provenance_hit"] is True
        assert manifest["verification_report"] == expected_report
        assert manifest["license_scan"] == expected_license
        assert manifest["secret_scan"] == expected_secret
        # Nothing from the prior manifest was substituted in.
        prior = _prior_manifest()
        assert manifest["verification_report"] != prior["verification_report"]
        assert manifest["license_scan"] != prior["license_scan"]
        assert manifest["secret_scan"] != prior["secret_scan"]

    # The inputs the caller handed over were not altered.
    assert field(inputs, "verification_report") == passed_report
    assert field(inputs, "license_scan_result") == passed_license
    assert field(inputs, "secret_scan_result") == passed_secret
    assert passed_report == expected_report
    assert passed_license == expected_license
    assert passed_secret == expected_secret

    # No lookup was performed by this component itself.
    log = repo_root / "invocations.log"
    calls = []
    if log.exists():
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert calls == [], f"write_provenance performed lookups itself: {calls}"