# hotdocs-criterion: sha256:a484316602c5a0ae03fcdb82e4290b70a5cde2cf86f242402647f0cb0d51dfce
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.97,
    "mutation_error": None,
    "assets": [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": "sha256:feedfacefeedface",
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "overall": "pass",
}

LICENSE_SCAN = {
    "blocked": True,
    "findings": [{"path": "foo.py", "license": "GPL-3.0-only", "marker": "from-tracker-license"}],
}

SECRET_SCAN = {
    "flagged": True,
    "findings": [{"path": "foo.py", "line": 7, "kind": "aws-key", "marker": "from-tracker-secret"}],
}

CAPABILITY_SCENARIO_REPORT = {
    "P-ZERO-EDIT": {
        "overall": "pass",
        "scenarios": [{"id": "S-ZERO-EDIT-001", "result": "pass", "marker": "from-tracker-capability"}],
    }
}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": False,
    "components": {
        "comp-foo": {
            "hit": True,
            "reason": None,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": LICENSE_SCAN,
            "secret_scan": SECRET_SCAN,
        }
    },
    "capabilities": {
        "P-ZERO-EDIT": {
            "hit": True,
            "capability_scenario_report": CAPABILITY_SCENARIO_REPORT,
        }
    },
    "not_ready_reasons": ["comp-foo: license scan blocked"],
}

FORBIDDEN = [
    ("verifier-orchestrator", "verifier_orchestrator"),
    ("license-scanner", "license_scanner"),
    ("secret-scanner", "secret_scanner"),
    ("capability-scenario-verifier", "capability_scenario_verifier"),
    ("provenance-checker", "provenance_checker"),
]


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        env=env,
        check=True,
        capture_output=True,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_fixture(repo_root, tracker_log, forbidden_log):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n\n# Foo\n\nA fixture component.\n",
    )
    _write(comp / "requirements" / "R-FOO-001.md", "**R-FOO-001** — Foo MUST do foo.\n")
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\nFoo does foo.\n",
    )
    _write(comp / "interface" / "library.md", "# Library\n\nfoo() -> None\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "specs" / "product" / "P-ZERO-EDIT.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero edit\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n\n# P-ZERO-EDIT\n\nZero-edit capability.\n",
    )

    tracker_src = (
        "import json\n"
        "\n"
        "_LOG = " + repr(str(tracker_log)) + "\n"
        "_REPORT = " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'fn': 'check_readiness', 'changed_ids': changed_ids}) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_src)

    for slug, module_name in FORBIDDEN:
        src = (
            "_LOG = " + repr(str(forbidden_log)) + "\n"
            "_SLUG = " + repr(slug) + "\n"
            "\n"
            "def __getattr__(name):\n"
            "    if name.startswith('__'):\n"
            "        raise AttributeError(name)\n"
            "    def _forbidden(*args, **kwargs):\n"
            "        with open(_LOG, 'a') as fh:\n"
            "            fh.write(_SLUG + '.' + name + '\\n')\n"
            "        raise RuntimeError('forbidden live call: ' + _SLUG + '.' + name)\n"
            "    return _forbidden\n"
        )
        _write(repo_root / "gen" / slug / (module_name + ".py"), src)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")


def test_ac_packet_011_fields_read_only_from_verify_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    tracker_log = logs / "tracker.log"
    forbidden_log = logs / "forbidden.log"
    _build_fixture(repo_root, tracker_log, forbidden_log)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001", "AC-FOO-001"], repo_root
    )

    # provenance-tracker's check_readiness was the read source
    assert tracker_log.is_file(), "check_readiness was never called"
    assert tracker_log.read_text().strip() != ""

    # no live call into any of the underlying components
    calls = forbidden_log.read_text() if forbidden_log.exists() else ""
    assert calls.strip() == "", "unexpected live calls: " + calls

    # verification_results from VerifyReport.components[...].verification_report
    verification_results = field(packet, "verification_results")
    assert "comp-foo" in verification_results
    assert verification_results["comp-foo"] == VERIFICATION_REPORT

    # compliance_flags from license_scan / secret_scan
    compliance_flags = field(packet, "compliance_flags")
    license_entries = field(compliance_flags, "license_scan")
    secret_entries = field(compliance_flags, "secret_scan")
    assert len(license_entries) == 1
    assert field(license_entries[0], "component_id") == "comp-foo"
    assert field(license_entries[0], "result") == LICENSE_SCAN
    assert len(secret_entries) == 1
    assert field(secret_entries[0], "component_id") == "comp-foo"
    assert field(secret_entries[0], "result") == SECRET_SCAN

    # provenance_hit_status from the real `hit` field
    provenance_hit_status = field(packet, "provenance_hit_status")
    assert provenance_hit_status.get("comp-foo") is True

    # capability_scenarios from VerifyReport.capabilities, report kept wrapped by P-id
    capability_scenarios = field(packet, "capability_scenarios")
    assert "P-ZERO-EDIT" in capability_scenarios
    assert capability_scenarios["P-ZERO-EDIT"] == CAPABILITY_SCENARIO_REPORT
    # distinct section, never conflated with verification_results
    assert "P-ZERO-EDIT" not in verification_results