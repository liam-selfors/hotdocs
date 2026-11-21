# hotdocs-criterion: sha256:2e7725c6c6bc1ce534e00844c3c6eb7eb23d422e7e9d63ae7a8ef05277feac77
import importlib.util
import subprocess
import sys
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com"] + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do foo.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo happens\n```\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return 1\n")

    stand_in = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return " + repr(_verify_report()) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", stand_in)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")
    return repo_root


def test_ac_packet_005_compliance_flags_explicitly_empty_when_clean(tmp_path):
    repo_root = _build_repo(tmp_path)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    assert has_field(packet, "compliance_flags"), "compliance_flags section must be present"
    flags = field(packet, "compliance_flags")
    assert flags is not None

    assert has_field(flags, "license_scan"), "license_scan must be present, not omitted"
    assert has_field(flags, "secret_scan"), "secret_scan must be present, not omitted"

    license_scan = field(flags, "license_scan")
    secret_scan = field(flags, "secret_scan")

    assert license_scan is not None
    assert secret_scan is not None
    assert list(license_scan) == []
    assert list(secret_scan) == []
    assert isinstance(license_scan, list)
    assert isinstance(secret_scan, list)