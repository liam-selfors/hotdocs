import json
import textwrap

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_repo_root(tmp_path, capability_id="P-FOO", component_slug="alpha"):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    component_id = f"comp-{component_slug}"

    # Not sealed: this criterion concerns realizes/capability-linkage, so the
    # fixture needs a resolvable realizes edge rather than the sealed default.
    _write(
        repo_root / "specs" / "components" / component_slug / "component.md",
        textwrap.dedent(f"""\
            ---
            id: {component_id}
            title: Alpha Component
            status: ratified
            last_ratified_commit: abc1234
            owners: [lselfors@gmail.com]
            realizes: [{capability_id}]
            ---

            # {component_id}

            A fixture component realizing {capability_id}.
            """),
    )

    _write(
        repo_root / "specs" / "components" / component_slug / "requirements" / "R-ALPHA-001.md",
        "The component MUST do the fixture thing.\n",
    )

    _write(
        repo_root / "specs" / "components" / component_slug / "acceptance" / "AC-ALPHA-001.md",
        textwrap.dedent("""\
            # AC-ALPHA-001

            Covers: R-ALPHA-001

            Given a fixture state
            When evaluated
            Then it passes
            """),
    )

    _write(
        repo_root / "specs" / "product" / "foo.md",
        textwrap.dedent(f"""\
            ---
            id: {capability_id}
            title: Foo capability
            status: ratified
            last_ratified_commit: abc1234
            owners: [lselfors@gmail.com]
            ---

            # {capability_id}

            A fixture product capability realized by {component_id}.
            """),
    )

    return repo_root, component_id


def _install_provenance_checker_fake(repo_root):
    module_dir = repo_root / "gen" / "provenance-checker"
    module_dir.mkdir(parents=True, exist_ok=True)
    source = textwrap.dedent("""
        from dataclasses import dataclass


        @dataclass
        class ProvenanceKey:
            spec_bundle_hash: str
            gate_versions: dict


        @dataclass
        class ProvenanceCheckResult:
            hit: bool
            verification_report: object
            license_scan: object
            secret_scan: object


        def current_provenance_key(component_id, repo_root):
            return ProvenanceKey(
                spec_bundle_hash="sha256:" + "a" * 64,
                gate_versions={
                    "compiler": "criterion-compiler@1.0.0",
                    "generated_test": "generated_test@1.0.0",
                    "verifier": "verifier-orchestrator@2.0.0",
                    "license_scanner": "license_scanner@3.1.0",
                    "secret_scanner": "secret_scanner@0.0.0",
                },
            )


        def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
            verification_report = {
                "component_id": component_id,
                "criteria": [
                    {"id": "AC-ALPHA-001", "covers": "R-ALPHA-001", "kind": "generated-test", "result": "pass"},
                ],
                "requirement_results": {"R-ALPHA-001": "pass"},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            }
            license_scan = {
                "component_id": component_id,
                "gate_version": "license_scanner@3.1.0",
                "similarity_score": 0.0,
                "block_threshold": 0.70,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }
            secret_scan = {
                "scope": "full",
                "gate_version": "secret_scanner@2.0.0",
                "flagged": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }
            return ProvenanceCheckResult(
                hit=True,
                verification_report=verification_report,
                license_scan=license_scan,
                secret_scan=secret_scan,
            )
    """)
    (module_dir / "provenance_checker.py").write_text(source)


def _install_capability_scenario_verifier_fake(
    repo_root, capability_id, *, provenance_hit, capability_overall, invocation_log
):
    # check_capability_provenance always reports a miss here: a hit would
    # short-circuit before run_capability_gates is ever called (AC-TRACK-010).
    module_dir = repo_root / "gen" / "capability-scenario-verifier"
    module_dir.mkdir(parents=True, exist_ok=True)
    template = textwrap.dedent("""
        import json
        from dataclasses import dataclass


        @dataclass
        class CapabilityProvenanceCheckResult:
            hit: bool
            capability_scenario_report: object


        _CAPABILITY_ID = __CAPABILITY_ID__
        _PROVENANCE_HIT = __PROVENANCE_HIT__
        _CAPABILITY_OVERALL = __CAPABILITY_OVERALL__
        _INVOCATION_LOG = __INVOCATION_LOG__


        def check_capability_provenance(capability_id, repo_root):
            return CapabilityProvenanceCheckResult(
                hit=_PROVENANCE_HIT,
                capability_scenario_report=None,
            )


        def run_capability_gates(capability_id, repo_root, judge=None, test_author=None):
            with open(_INVOCATION_LOG, "a") as f:
                f.write(json.dumps({"capability_id": capability_id}) + "\\n")
            report = {
                _CAPABILITY_ID: {
                    "overall": _CAPABILITY_OVERALL,
                    "scenarios": [
                        {"id": "CS-FOO-001", "kind": "generated-test", "result": _CAPABILITY_OVERALL},
                    ],
                },
            }
            return CapabilityProvenanceCheckResult(hit=True, capability_scenario_report=report)


        def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
            raise AssertionError("run_capability_scenarios must never be called by check_readiness")
    """)
    source = (
        template
        .replace("__CAPABILITY_ID__", repr(capability_id))
        .replace("__PROVENANCE_HIT__", repr(provenance_hit))
        .replace("__CAPABILITY_OVERALL__", repr(capability_overall))
        .replace("__INVOCATION_LOG__", repr(str(invocation_log)))
    )
    (module_dir / "capability_scenario_verifier.py").write_text(source)


def test_all_components_and_intersecting_capabilities_pass(tmp_path):
    capability_id = "P-FOO"
    repo_root, component_id = _make_repo_root(tmp_path, capability_id=capability_id)
    invocation_log = tmp_path / "run_capability_gates.log"

    _install_provenance_checker_fake(repo_root)
    _install_capability_scenario_verifier_fake(
        repo_root,
        capability_id,
        provenance_hit=False,
        capability_overall="pass",
        invocation_log=invocation_log,
    )

    report = provenance_tracker.check_readiness(repo_root, model="gpt-5", seed=0)

    assert _get(report, "ready") is True
    assert len(_get(report, "not_ready_reasons", [])) == 0

    assert invocation_log.exists()
    lines = invocation_log.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["capability_id"] == capability_id

    components = _get(report, "components")
    comp_entry = _get(components, component_id)
    assert _get(comp_entry, "hit") is True

    capabilities = _get(report, "capabilities")
    cap_entry = _get(capabilities, capability_id)
    assert _get(cap_entry, "hit") is True
    scenario_report = _get(cap_entry, "capability_scenario_report")
    assert _get(_get(scenario_report, capability_id), "overall") == "pass"


def test_one_failing_capability_blocks_readiness_despite_passing_components(tmp_path):
    capability_id = "P-FOO"
    repo_root, component_id = _make_repo_root(tmp_path, capability_id=capability_id)
    invocation_log = tmp_path / "run_capability_gates.log"

    _install_provenance_checker_fake(repo_root)
    _install_capability_scenario_verifier_fake(
        repo_root,
        capability_id,
        provenance_hit=False,
        capability_overall="fail",
        invocation_log=invocation_log,
    )

    report = provenance_tracker.check_readiness(repo_root, model="gpt-5", seed=0)

    assert _get(report, "ready") is False

    not_ready_reasons = _get(report, "not_ready_reasons", [])
    assert any(capability_id in reason for reason in not_ready_reasons)

    components = _get(report, "components")
    comp_entry = _get(components, component_id)
    assert _get(comp_entry, "hit") is True
    verification_report = _get(comp_entry, "verification_report")
    assert _get(verification_report, "overall") == "pass"

    assert invocation_log.exists()
    assert len(invocation_log.read_text().splitlines()) == 1


def test_capability_miss_with_no_model_is_usage_error(tmp_path):
    capability_id = "P-FOO"
    repo_root, component_id = _make_repo_root(tmp_path, capability_id=capability_id)
    invocation_log = tmp_path / "run_capability_gates.log"

    _install_provenance_checker_fake(repo_root)
    _install_capability_scenario_verifier_fake(
        repo_root,
        capability_id,
        provenance_hit=False,
        capability_overall="pass",
        invocation_log=invocation_log,
    )

    try:
        report = provenance_tracker.check_readiness(repo_root, model=None)
    except Exception as exc:
        message = str(exc)
        assert capability_id in message
        assert "model" in message.lower()
    else:
        assert _get(report, "ready") is False
        not_ready_reasons = _get(report, "not_ready_reasons", [])
        matching = [
            reason
            for reason in not_ready_reasons
            if capability_id in reason and "model" in reason.lower()
        ]
        assert matching

    # run_capability_gates's fake only ever creates this file when invoked.
    assert not invocation_log.exists()