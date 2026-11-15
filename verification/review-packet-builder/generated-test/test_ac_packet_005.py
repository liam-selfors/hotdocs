import json
import os
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_component(repo_root, slug, upper):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} fixture component\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n\n"
        f"# comp-{slug}\n\nA synthetic fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\ndo_thing() -> None\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / slug / f"{slug}.py", "def do_thing():\n    return None\n")


def _verification_report(component_id, upper):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": f"AC-{upper}-001",
                "covers": f"R-{upper}-001",
                "kind": "generated-test",
                "result": "pass",
            }
        ],
        "requirement_results": {f"R-{upper}-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "overall": "pass",
    }


def _provenance_check_result(component_id, upper):
    return {
        "hit": True,
        "verification_report": _verification_report(component_id, upper),
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")

    _write_component(root, "foo", "FOO")
    _write_component(root, "bar", "BAR")

    log_path = tmp_path / "tracker_calls.log"
    verify_report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": _provenance_check_result("comp-foo", "FOO"),
            "comp-bar": _provenance_check_result("comp-bar", "BAR"),
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }

    stand_in = (
        "import json\n"
        f"_LOG_PATH = {str(log_path)!r}\n"
        f"_REPORT = {verify_report!r}\n"
        "\n"
        "\n"
        "def _log(record):\n"
        "    with open(_LOG_PATH, 'a') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log({'fn': 'check_readiness', 'changed_ids': list(changed_ids) if changed_ids is not None else None})\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log({'fn': 'last_requirement_failures', 'component_id': component_id})\n"
        "    return []\n"
    )
    _write(root / "gen" / "provenance-tracker" / "provenance_tracker.py", stand_in)

    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial fixture")

    return root, log_path


def test_compliance_flags_present_and_explicitly_empty_when_scans_clean(repo_root):
    root, log_path = repo_root
    changed_ids = ["comp-foo", "R-FOO-001", "comp-bar", "R-BAR-001"]

    packet = review_packet_builder.build_review_packet(changed_ids, root)

    # The stand-in provenance-tracker was actually consulted.
    assert log_path.exists(), "provenance-tracker stand-in was never invoked"
    calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert any(c["fn"] == "check_readiness" for c in calls)

    # compliance_flags is its own explicit section, present (not omitted).
    assert has_field(packet, "compliance_flags"), "compliance_flags section omitted"
    flags = field(packet, "compliance_flags")
    assert flags is not None, "compliance_flags must be present, not null"

    # Both fields present, explicitly empty lists — not omitted, not None.
    assert has_field(flags, "license_scan"), "compliance_flags.license_scan omitted"
    assert has_field(flags, "secret_scan"), "compliance_flags.secret_scan omitted"

    license_flags = field(flags, "license_scan")
    secret_flags = field(flags, "secret_scan")

    assert license_flags is not None
    assert secret_flags is not None
    assert list(license_flags) == []
    assert list(secret_flags) == []
    assert isinstance(license_flags, (list, tuple))
    assert isinstance(secret_flags, (list, tuple))