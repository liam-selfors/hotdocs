# hotdocs-criterion: sha256:cdfafcbb6ab6eface0972fe72903f98da4ede59d867f8d4c02c702fd7026d81f
import shutil
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write_component(repo_root, slug, prefix):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " component\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# comp-" + slug + "\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / ("R-" + prefix + "-001.md"),
        "# R-" + prefix + "-001\n\n"
        "**R-" + prefix + "-001** — The component MUST do its one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / ("AC-" + prefix + "-001.md"),
        "# AC-" + prefix + "-001\n\n"
        "Covers: R-" + prefix + "-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the component\n"
        "When it runs\n"
        "Then it does its one thing\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\ndo_thing() -> None\n```\n",
    )
    _write(repo_root / "legacy" / slug / "__init__.py", "")


def _verification_report(component_id, prefix):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-" + prefix + "-001",
                "covers": "R-" + prefix + "-001",
                "kind": "generated-test",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-" + prefix + "-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": "pass",
    }


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_provenance_hit_status_per_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _git(repo_root, "init", "-q")
    _write(repo_root / "README.md", "fixture\n")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    _write_component(repo_root, "foo", "FOO")
    _write_component(repo_root, "bar", "BAR")

    verify_report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report("comp-foo", "FOO"),
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-bar": {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state — run hotdocs generate comp-bar"
        ],
    }

    tracker_src = (
        "REPORT = " + repr(verify_report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_src,
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add fixture components")

    changed_ids = ["comp-foo", "comp-bar", "R-FOO-001", "R-BAR-001"]
    packet = review_packet_builder.build_review_packet(changed_ids, repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    status = field(packet, "provenance_hit_status")
    assert "comp-foo" in status, "provenance_hit_status missing entry for comp-foo"
    assert "comp-bar" in status, "provenance_hit_status missing entry for comp-bar"
    assert status["comp-foo"] is True
    assert status["comp-bar"] is False