"""AC-TRACK-013 (covers R-TRACK-009): sealed vs. generated routing in check_readiness."""

import json
import sys
from pathlib import Path

import provenance_tracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SEAL_ID = "comp-seal"
PLAIN_ID = "comp-plain"

SEALED_HIT = {
    "hit": True,
    "sealed": True,
    "reason": None,
    "verification_report": {"overall": "pass"},
    "license_scan": None,
    "secret_scan": None,
    "owners": ["pipeline-team"],
    "source_hash": "sha256:" + "0" * 64,
    "written_at": "2026-11-02T00:00:00Z",
}

SEALED_MISS_SOURCE_CHANGED = {
    "hit": False,
    "sealed": True,
    "reason": "source_changed",
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
    "owners": None,
    "source_hash": None,
    "written_at": None,
}

PLAIN_VERIFICATION_REPORT = {
    "component_id": PLAIN_ID,
    "criteria": [
        {"id": "AC-PLAIN-001", "covers": "R-PLAIN-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-PLAIN-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "overall": "pass",
}

PLAIN_LICENSE_SCAN = {
    "component_id": PLAIN_ID,
    "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
    "evaluated": True,
    "reason": None,
    "similarity_score": 0.1,
    "block_threshold": 0.7,
    "blocked": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

PLAIN_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@0.0.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

PLAIN_HIT = {
    "hit": True,
    "verification_report": PLAIN_VERIFICATION_REPORT,
    "license_scan": PLAIN_LICENSE_SCAN,
    "secret_scan": PLAIN_SECRET_SCAN,
}

FLAGGED_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@0.0.0",
    "flagged": True,
    "matches": [
        {"rule_id": "Generic Token", "risk_tier": "high", "file": "legacy/seal/seal.py", "line": 1}
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


FAKE_PROVENANCE_CHECKER = '''
import json
from pathlib import Path

_LOG = Path(__LOG_PATH__)
_SEALED_RESULT_PATH = Path(__SEALED_PATH__)
_PLAIN_RESULT_PATH = Path(__PLAIN_PATH__)
_SEALED_IDS = ("comp-seal",)


def _log(name, *args):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": name, "args": list(args)}, default=str) + "\\n")


class _Attrs:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getitem__(self, key):
        return self.__dict__[key]

    def get(self, key, default=None):
        return self.__dict__.get(key, default)


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id, str(repo_root))
    if component_id in _SEALED_IDS:
        return _Attrs(
            owners=["pipeline-team"],
            source_path="legacy/seal/",
            source_hash="sha256:" + "0" * 64,
            verifier_version="verifier-orchestrator@2.0.0",
        )
    return None


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id, str(repo_root))
    return json.loads(_SEALED_RESULT_PATH.read_text(encoding="utf-8"))


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id, str(repo_root))
    return _Attrs(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id, spec_bundle_hash, gate_versions, str(repo_root))
    return json.loads(_PLAIN_RESULT_PATH.read_text(encoding="utf-8"))
'''


FAKE_GATE_RUNNER = '''
import json
from pathlib import Path

_LOG = Path(__LOG_PATH__)

with open(_LOG, "a", encoding="utf-8") as _fh:
    _fh.write(json.dumps({"name": "component_gate_runner_loaded", "args": []}) + "\\n")


def run_component_gates(*args, **kwargs):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": "run_component_gates", "args": [str(a) for a in args]}) + "\\n")
    raise RuntimeError("component-gate-runner must never be called by check_readiness")
'''


FAKE_CAPABILITY_VERIFIER = '''
GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    return {}


def check_capability_provenance(capability_id, repo_root):
    return {
        "hit": True,
        "capability_scenario_report": {capability_id: {"overall": "pass", "scenarios": []}},
    }


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    return {
        "hit": True,
        "capability_scenario_report": {capability_id: {"overall": "pass", "scenarios": []}},
    }
'''


FAKE_SECRET_SCANNER = '''
import json

GATE_VERSION = "secret_scanner@0.0.0"

_FLAGGED = json.loads(__FLAGGED_JSON__)


def gate_version(repo_root):
    return GATE_VERSION


def _flagged(*args, **kwargs):
    return dict(_FLAGGED)


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return _flagged
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root: Path, slug: str, sealed: bool) -> None:
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    frontmatter = [
        "---",
        f"id: comp-{slug}",
        f"title: {slug.capitalize()} component",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "realizes: []",
        f"sealed: {'true' if sealed else 'false'}",
    ]
    if sealed:
        frontmatter.append(f"source_path: legacy/{slug}/")
    frontmatter.append("---")
    _write(
        comp_dir / "component.md",
        "\n".join(frontmatter) + f"\n\n# comp-{slug}\n\nA fixture component.\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — MUST do its one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    if sealed:
        _write(repo_root / "legacy" / slug / f"{slug}.py", "VALUE = 1\n")
    else:
        _write(repo_root / "gen" / slug / f"{slug}.py", "VALUE = 1\n")


def _build_repo(tmp_path: Path, sealed_result: dict, flagged_secret: bool = False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.jsonl"
    log_path.write_text("", encoding="utf-8")
    sealed_path = tmp_path / "sealed_result.json"
    sealed_path.write_text(json.dumps(sealed_result), encoding="utf-8")
    plain_path = tmp_path / "plain_result.json"
    plain_path.write_text(json.dumps(PLAIN_HIT), encoding="utf-8")

    _write_component(repo_root, "seal", sealed=True)
    _write_component(repo_root, "plain", sealed=False)

    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        FAKE_PROVENANCE_CHECKER.replace("__LOG_PATH__", repr(str(log_path)))
        .replace("__SEALED_PATH__", repr(str(sealed_path)))
        .replace("__PLAIN_PATH__", repr(str(plain_path))),
    )
    _write(
        repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py",
        FAKE_GATE_RUNNER.replace("__LOG_PATH__", repr(str(log_path))),
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        FAKE_CAPABILITY_VERIFIER,
    )

    if flagged_secret:
        _write(
            repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
            FAKE_SECRET_SCANNER.replace(
                "__FLAGGED_JSON__", repr(json.dumps(FLAGGED_SECRET_SCAN))
            ),
        )
        for name in ("secret-scan.json", "secret_scan.json"):
            _write(repo_root / ".hotdocs" / name, json.dumps(FLAGGED_SECRET_SCAN))

    return repo_root, log_path


def _read_log(log_path: Path):
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _ids_called(entries, name):
    return [e["args"][0] for e in entries if e["name"] == name]


def _run(repo_root: Path):
    before = set(sys.modules)
    report = provenance_tracker.check_readiness(repo_root)
    added = set(sys.modules) - before
    return report, added


def _assert_gate_runner_never_loaded(entries, added_modules):
    names = [e["name"] for e in entries]
    assert "component_gate_runner_loaded" not in names
    assert "run_component_gates" not in names
    for key in added_modules:
        assert "component_gate_runner" not in key
        assert "component-gate-runner" not in key
        mod = sys.modules.get(key)
        mod_file = getattr(mod, "__file__", None) or ""
        assert "component-gate-runner" not in str(mod_file)
        assert "component_gate_runner" not in str(mod_file)


def _assert_equals_sealed(entry, expected):
    if isinstance(entry, dict):
        assert entry == expected
    else:
        for key, value in expected.items():
            assert field(entry, key) == value


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def test_sealed_hit_routes_through_check_sealed_provenance_only(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, SEALED_HIT)

    report, added = _run(repo_root)
    entries = _read_log(log_path)

    assert field(report, "ready") is True

    sealed_ids = _ids_called(entries, "check_sealed_provenance")
    assert sealed_ids, "check_sealed_provenance was never called"
    assert set(sealed_ids) == {SEAL_ID}

    prov_ids = _ids_called(entries, "check_provenance")
    assert prov_ids, "check_provenance was never called"
    assert set(prov_ids) == {PLAIN_ID}

    key_ids = _ids_called(entries, "current_provenance_key")
    assert key_ids, "current_provenance_key was never called"
    assert set(key_ids) == {PLAIN_ID}

    components = field(report, "components")
    assert SEAL_ID in components
    _assert_equals_sealed(components[SEAL_ID], SEALED_HIT)

    _assert_gate_runner_never_loaded(entries, added)


def test_sealed_miss_reports_exact_reason(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, SEALED_MISS_SOURCE_CHANGED)

    report, added = _run(repo_root)
    entries = _read_log(log_path)

    assert field(report, "ready") is False

    reasons = list(field(report, "not_ready_reasons"))
    seal_reasons = [r for r in reasons if SEAL_ID in r]
    assert seal_reasons == [
        "comp-seal: sealed provenance source_changed — run hotdocs generate comp-seal"
    ]

    _assert_gate_runner_never_loaded(entries, added)


def test_sealed_readiness_ignores_flagged_repository_secret_scan(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, SEALED_HIT, flagged_secret=True)

    report, added = _run(repo_root)
    entries = _read_log(log_path)

    assert set(_ids_called(entries, "check_sealed_provenance")) == {SEAL_ID}

    components = field(report, "components")
    assert SEAL_ID in components
    _assert_equals_sealed(components[SEAL_ID], SEALED_HIT)
    assert field(components[SEAL_ID], "hit") is True

    reasons = list(field(report, "not_ready_reasons"))
    assert not [r for r in reasons if SEAL_ID in r], reasons

    _assert_gate_runner_never_loaded(entries, added)