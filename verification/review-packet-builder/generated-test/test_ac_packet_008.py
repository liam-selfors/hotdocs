import textwrap
from pathlib import Path

import review_packet_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_PROVENANCE_TRACKER = textwrap.dedent('''\
    from pathlib import Path


    def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        log_path = Path(repo_root) / "provenance_tracker_invocations.log"
        with open(log_path, "a") as f:
            f.write("called")

        widget_report = {
            "component_id": "comp-widget",
            "criteria": [
                {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001", "kind": "compiled", "result": "pass"},
            ],
            "requirement_results": {"R-WIDGET-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "pass",
        }

        gadget_report = {
            "component_id": "comp-gadget",
            "criteria": [
                {"id": "AC-GADGET-001", "covers": "R-GADGET-001", "kind": "compiled", "result": "pass"},
            ],
            "requirement_results": {"R-GADGET-001": "pass"},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        }

        return {
            "scope": "blast-radius",
            "ready": True,
            "components": {
                "comp-widget": {
                    "hit": True,
                    "verification_report": widget_report,
                    "license_scan": {"blocked": False, "findings": []},
                    "secret_scan": {"flagged": False, "findings": []},
                },
                "comp-gadget": {
                    "hit": True,
                    "verification_report": gadget_report,
                    "license_scan": {"blocked": False, "findings": []},
                    "secret_scan": {"flagged": False, "findings": []},
                },
            },
            "capabilities": {},
            "not_ready_reasons": [],
        }
''')


def _write_sealed_component(repo_root, slug, component_id, req_id, ac_id):
    comp_dir = repo_root / "specs" / "components" / slug
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)

    component_md = textwrap.dedent(f'''\
        ---
        id: {component_id}
        title: {slug.capitalize()}
        status: ratified
        owners: [team-{slug}]
        last_ratified_commit: 0000000
        sealed: true
        source_path: legacy/{slug}.py
        ---

        # {component_id}

        A sealed legacy component used only as a review-packet-builder test fixture.
        ''')
    (comp_dir / "component.md").write_text(component_md)

    requirement_md = textwrap.dedent(f'''\
        # {req_id}

        **{req_id}** -- the {slug} component MUST do its one documented thing.
        ''')
    (comp_dir / "requirements" / f"{req_id.lower().replace('-', '_')}.md").write_text(requirement_md)

    acceptance_md = textwrap.dedent(f'''\
        # {ac_id}

        Covers: {req_id}
        Kind: compiled

        ```gherkin
        Given the {slug} component
        When it runs
        Then it behaves as documented
        ```
        ''')
    (comp_dir / "acceptance" / f"{ac_id.lower().replace('-', '_')}.md").write_text(acceptance_md)


def test_residual_risk_includes_passing_component_with_low_mutation_score(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_sealed_component(repo_root, "widget", "comp-widget", "R-WIDGET-001", "AC-WIDGET-001")
    _write_sealed_component(repo_root, "gadget", "comp-gadget", "R-GADGET-001", "AC-GADGET-001")

    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True)
    (dep_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER)

    packet = review_packet_builder.build_review_packet(
        ["comp-widget", "comp-gadget"], repo_root
    )

    log_path = repo_root / "provenance_tracker_invocations.log"
    assert log_path.exists(), "fake provenance-tracker.check_readiness was never invoked"

    residual_risk = _get(packet, "residual_risk")
    assert residual_risk is not None

    widget_entries = [
        entry for entry in residual_risk if _get(entry, "component_id") == "comp-widget"
    ]
    assert len(widget_entries) == 1, (
        f"expected exactly one residual_risk finding for comp-widget, got {widget_entries}"
    )
    message = _get(widget_entries[0], "message")
    assert isinstance(message, str)
    assert "0.92" in message

    gadget_entries = [
        entry for entry in residual_risk if _get(entry, "component_id") == "comp-gadget"
    ]
    assert gadget_entries == [], (
        "comp-gadget has mutation_score 1.0 and should not appear in residual_risk"
    )

    verification_results = _get(packet, "verification_results")
    widget_verification = _get(verification_results, "comp-widget")
    assert _get(widget_verification, "overall") == "pass"
    assert _get(widget_verification, "mutation_score") == 0.92