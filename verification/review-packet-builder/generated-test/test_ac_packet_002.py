# hotdocs-criterion: sha256:34232960f16b2b6f3d4891ba08a7885976482d3e6435021c5253eb6015da1690
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _verify_report():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": "pass",
    }
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _build_fixture(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the first thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does the first thing\n```\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "VALUE = 1\n")

    stub_source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return " + repr(_verify_report()) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        stub_source,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    # The PR: add one new requirement R-FOO-002 (with its acceptance criterion).
    _write(
        comp_dir / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do the second thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does the second thing\n```\n",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add R-FOO-002")


def test_changed_requirements_includes_new_requirement(tmp_path):
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root)

    packet = review_packet_builder.build_review_packet(
        ["R-FOO-002", "AC-FOO-002"], Path(repo_root)
    )

    changed_requirements = list(field(packet, "changed_requirements"))
    assert "R-FOO-002" in changed_requirements