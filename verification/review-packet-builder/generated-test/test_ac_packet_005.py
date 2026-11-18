# hotdocs-criterion: sha256:c632c121be610c2f70201312b3baafc80b8365e527e64ccab6c2fd37b184ecd1
import subprocess
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
        [
            "git",
            "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
        ]
        + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _build_fixture(repo_root, log_path):
    # Minimal synthetic spec corpus: one sealed component.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# comp-foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen foo runs\nThen the thing is done\n```\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "VALUE = 1\n")

    verification_report = {
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
        "mutation_score": None,
        "mutation_error": None,
        "overall": "pass",
    }
    license_scan = {
        "component_id": "comp-foo",
        "blocked": False,
        "findings": [],
    }
    secret_scan = {
        "component_id": "comp-foo",
        "flagged": False,
        "findings": [],
    }
    verify_report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report,
                "license_scan": license_scan,
                "secret_scan": secret_scan,
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }

    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    report = copy.deepcopy(REPORT)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return report\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        source,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial fixture")


def test_clean_scans_yield_explicitly_empty_compliance_flags(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _build_fixture(repo_root, log_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )

    # The provenance-tracker stand-in was actually consulted.
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    # compliance_flags is present as its own section, not omitted.
    assert has_field(packet, "compliance_flags")
    flags = field(packet, "compliance_flags")
    assert flags is not None

    # Both fields are explicitly present...
    assert has_field(flags, "license_scan")
    assert has_field(flags, "secret_scan")

    license_flags = field(flags, "license_scan")
    secret_flags = field(flags, "secret_scan")

    # ...and explicitly empty lists, not None / omitted.
    assert license_flags is not None
    assert secret_flags is not None
    assert list(license_flags) == []
    assert list(secret_flags) == []
    assert isinstance(license_flags, (list, tuple))
    assert isinstance(secret_flags, (list, tuple))