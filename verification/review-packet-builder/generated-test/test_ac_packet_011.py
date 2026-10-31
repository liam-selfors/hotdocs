import textwrap
from pathlib import Path

import review_packet_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


COMPONENT_MD = textwrap.dedent(
    """\
    ---
    id: comp-foo
    title: Foo
    status: ratified
    owners: [lselfors@gmail.com]
    last_ratified_commit: 0000000
    sealed: true
    source_path: ../../legacy/foo.py
    depends_on: []
    ---

    # comp-foo

    A fixture component used only to exercise comp-review-packet-builder's
    AC-PACKET-011 sourcing behavior.
    """
)

REQUIREMENT_MD = textwrap.dedent(
    """\
    # R-FOO-001

    **R-FOO-001** -- Foo must do the foo thing.
    """
)

ACCEPTANCE_MD = textwrap.dedent(
    """\
    # AC-FOO-001

    Covers: R-FOO-001
    Kind: compiled

    Foo does the foo thing.
    """
)

PROVENANCE_TRACKER_MODULE = textwrap.dedent(
    """\
    VERIFY_REPORT = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "covers": "R-FOO-001",
                            "kind": "compiled",
                            "result": "pass",
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {
                    "component_id": "comp-foo",
                    "blocked": True,
                    "findings": ["GPL-3.0 dependency detected"],
                },
                "secret_scan": {
                    "component_id": "comp-foo",
                    "flagged": True,
                    "findings": ["possible API key in foo.py"],
                },
            }
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "capability_id": "P-ZERO-EDIT",
                    "scenarios": [{"id": "SC-ZERO-EDIT-001", "result": "pass"}],
                    "overall": "pass",
                },
            }
        },
        "not_ready_reasons": [],
    }


    def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        return VERIFY_REPORT
    """
)

NO_CALL_MODULE = textwrap.dedent(
    """\
    import json
    from pathlib import Path

    _CALLS_FILE = Path(__file__).parent / "_calls.jsonl"


    def __getattr__(name):
        def _tracked(*args, **kwargs):
            with open(_CALLS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({"attr": name}) + "\\n")
            return {}

        return _tracked
    """
)


def test_ac_packet_011_sources_only_from_provenance_tracker(tmp_path):
    repo_root = tmp_path

    _write(repo_root / "specs/components/foo/component.md", COMPONENT_MD)
    _write(repo_root / "specs/components/foo/requirements/R-FOO-001.md", REQUIREMENT_MD)
    _write(repo_root / "specs/components/foo/acceptance/AC-FOO-001.md", ACCEPTANCE_MD)

    _write(
        repo_root / "gen/provenance-tracker/provenance_tracker.py",
        PROVENANCE_TRACKER_MODULE,
    )

    no_call_calls_files = {
        "gen/verifier-orchestrator/verifier_orchestrator.py": repo_root
        / "gen/verifier-orchestrator/_calls.jsonl",
        "gen/license-scanner/license_scanner.py": repo_root
        / "gen/license-scanner/_calls.jsonl",
        "gen/secret-scanner/secret_scanner.py": repo_root
        / "gen/secret-scanner/_calls.jsonl",
        "gen/capability-scenario-verifier/capability_scenario_verifier.py": repo_root
        / "gen/capability-scenario-verifier/_calls.jsonl",
    }
    for rel_module_path in no_call_calls_files:
        _write(repo_root / rel_module_path, NO_CALL_MODULE)

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    verification_results = _get(packet, "verification_results")
    vr_foo = _get(verification_results, "comp-foo")
    assert _get(vr_foo, "component_id") == "comp-foo"
    assert _get(vr_foo, "overall") == "pass"
    assert _get(vr_foo, "mutation_score") == 1.0
    requirement_results = _get(vr_foo, "requirement_results")
    assert _get(requirement_results, "R-FOO-001") == "pass"

    compliance_flags = _get(packet, "compliance_flags")
    license_flags = _get(compliance_flags, "license_scan")
    assert len(license_flags) == 1
    license_entry = license_flags[0]
    assert _get(license_entry, "component_id") == "comp-foo"
    assert _get(_get(license_entry, "result"), "blocked") is True

    secret_flags = _get(compliance_flags, "secret_scan")
    assert len(secret_flags) == 1
    secret_entry = secret_flags[0]
    assert _get(secret_entry, "component_id") == "comp-foo"
    assert _get(_get(secret_entry, "result"), "flagged") is True

    provenance_hit_status = _get(packet, "provenance_hit_status")
    assert _get(provenance_hit_status, "comp-foo") is True

    capability_scenarios = _get(packet, "capability_scenarios")
    cap_entry = _get(capability_scenarios, "P-ZERO-EDIT")
    assert _get(cap_entry, "capability_id") == "P-ZERO-EDIT"
    assert _get(cap_entry, "overall") == "pass"
    scenarios = _get(cap_entry, "scenarios")
    assert len(scenarios) == 1
    assert _get(scenarios[0], "id") == "SC-ZERO-EDIT-001"
    assert _get(scenarios[0], "result") == "pass"

    for calls_file in no_call_calls_files.values():
        assert not calls_file.exists(), f"unexpected live call recorded at {calls_file}"