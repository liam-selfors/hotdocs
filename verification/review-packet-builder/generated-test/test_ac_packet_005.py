import subprocess
import textwrap
from pathlib import Path

import review_packet_builder


def _run_git(repo_root, *args):
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def _init_repo_root(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _run_git(repo_root, "init")
    _run_git(repo_root, "config", "user.email", "test@example.com")
    _run_git(repo_root, "config", "user.name", "Test")

    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)

    (comp_dir / "component.md").write_text(textwrap.dedent("""\
        ---
        id: comp-foo
        title: Foo Component
        status: ratified
        owners: [lselfors]
        sealed: true
        source_path: vendor/foo/foo.py
        last_ratified_commit: 0000000000000000000000000000000000000000
        ---

        # Foo Component

        A sealed component used purely as a fixture for this test.
        """))

    (comp_dir / "requirements" / "R-FOO-001.md").write_text(textwrap.dedent("""\
        # R-FOO-001

        **R-FOO-001** — Foo must do the foo thing.
        """))

    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(textwrap.dedent("""\
        Covers: R-FOO-001

        ```gherkin
        Given a foo
        When it is fooed
        Then it foos
        ```
        """))

    pt_dir = repo_root / "gen" / "provenance-tracker"
    pt_dir.mkdir(parents=True)
    (pt_dir / "provenance_tracker.py").write_text(textwrap.dedent("""\
        def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
            return {
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
                                },
                            ],
                            "requirement_results": {"R-FOO-001": "pass"},
                            "interface_drift": False,
                            "mutation_score": None,
                            "overall": "pass",
                        },
                        "license_scan": {
                            "blocked": False,
                            "component_id": "comp-foo",
                            "findings": [],
                        },
                        "secret_scan": {
                            "flagged": False,
                            "component_id": "comp-foo",
                            "findings": [],
                        },
                    },
                },
                "capabilities": {},
                "not_ready_reasons": [],
            }


        def last_requirement_failures(component_id, repo_root):
            return []
        """))

    (repo_root / "README.md").write_text("fixture repo\n")
    _run_git(repo_root, "add", "-A")
    _run_git(repo_root, "commit", "-m", "initial commit")

    return repo_root


def test_compliance_flags_present_with_both_fields_explicitly_empty(tmp_path):
    repo_root = _init_repo_root(tmp_path)

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    assert _has_field(packet, "compliance_flags")
    compliance_flags = _field(packet, "compliance_flags")
    assert compliance_flags is not None

    assert _has_field(compliance_flags, "license_scan")
    assert _has_field(compliance_flags, "secret_scan")

    license_scan = _field(compliance_flags, "license_scan")
    secret_scan = _field(compliance_flags, "secret_scan")

    assert license_scan == []
    assert secret_scan == []