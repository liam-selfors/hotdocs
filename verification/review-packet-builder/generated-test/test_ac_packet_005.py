import review_packet_builder

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def _verification_report(component_id, r_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": ac_id,
                "covers": r_id,
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {r_id: "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "overall": "pass",
    }


def _clean_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(
                    "comp-foo", "R-FOO-001", "AC-FOO-001"
                ),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
            "comp-bar": {
                "hit": True,
                "verification_report": _verification_report(
                    "comp-bar", "R-BAR-001", "AC-BAR-001"
                ),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def _write_component(repo_root, slug, upper):
    comp_dir = repo_root / "specs" / "components" / slug
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [tester]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n\n"
        f"# comp-{slug}\n\nA synthetic fixture component.\n"
    )
    (comp_dir / "constraints.md").write_text("# Constraints\n\nNone.\n")
    (comp_dir / "interface" / "library.md").write_text(
        f"# Library\n\n```\n{slug}() -> None\n```\n"
    )
    (comp_dir / "requirements" / f"R-{upper}-001.md").write_text(
        f"# R-{upper}-001\n\n**R-{upper}-001** — The {slug} component MUST do its thing.\n"
    )
    (comp_dir / "acceptance" / f"AC-{upper}-001.md").write_text(
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n"
    )
    legacy = repo_root / "legacy" / slug
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / f"{slug}.py").write_text("def run():\n    return None\n")


def _write_tracker_stand_in(repo_root, log_path):
    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True, exist_ok=True)
    report_literal = repr(_clean_report())
    source = (
        "import copy\n"
        "\n"
        f"_LOG_PATH = {str(log_path)!r}\n"
        f"REPORT = {report_literal}\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    report = copy.deepcopy(REPORT)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return report\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(source)


@pytest.fixture
def repo_root(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to build the fixture repository")
    root = tmp_path / "repo"
    root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "tracker_calls.log"

    _git(root, "init", "-q")
    _write_component(root, "foo", "FOO")
    _write_component(root, "bar", "BAR")
    _write_tracker_stand_in(root, log_path)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial fixture")

    # A spec change after the commit, so a diff exists to report.
    req = root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
    req.write_text(
        "# R-FOO-001\n\n**R-FOO-001** — The foo component MUST do its thing well.\n"
    )
    return root, log_path


def test_clean_scans_yield_explicit_empty_compliance_flags(repo_root):
    root, log_path = repo_root
    changed_ids = ["comp-foo", "R-FOO-001", "comp-bar", "R-BAR-001"]

    packet = review_packet_builder.build_review_packet(changed_ids, Path(root))

    # The provenance-tracker stand-in was consulted.
    assert log_path.exists(), "provenance-tracker stand-in was never invoked"
    assert "check_readiness" in log_path.read_text()

    # compliance_flags is present, not omitted.
    assert has_field(packet, "compliance_flags"), "compliance_flags omitted from packet"
    flags = field(packet, "compliance_flags")
    assert flags is not None, "compliance_flags must be an explicit section, not None"

    # Both fields are explicitly present...
    assert has_field(flags, "license_scan"), "compliance_flags.license_scan omitted"
    assert has_field(flags, "secret_scan"), "compliance_flags.secret_scan omitted"

    license_flags = field(flags, "license_scan")
    secret_flags = field(flags, "secret_scan")

    # ...and explicitly empty lists, not None or missing.
    assert license_flags is not None
    assert secret_flags is not None
    assert list(license_flags) == []
    assert list(secret_flags) == []
    assert isinstance(license_flags, (list, tuple))
    assert isinstance(secret_flags, (list, tuple))