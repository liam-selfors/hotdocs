# hotdocs-criterion: sha256:86bbca3b7ae9d2bb163c08480b88a6827fe29b3969e08bc5c0e4f78a5bf46ff4
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
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
    _git(repo_root, "init", "-q")

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [foo-team]\n"
        "depends_on: []\n"
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
        "```gherkin\nGiven foo\nWhen it runs\nThen the first thing happens\n```\n",
    )

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

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    # The PR: adds one new requirement R-FOO-002 (and its criterion).
    _write(
        comp_dir / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do the second thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen the second thing happens\n```\n",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add R-FOO-002")

    return repo_root


def test_changed_requirements_includes_new_requirement(tmp_path):
    repo_root = _build_repo(tmp_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-002", "AC-FOO-002"], repo_root
    )

    changed_requirements = field(packet, "changed_requirements")
    assert isinstance(changed_requirements, (list, tuple))
    assert "R-FOO-002" in list(changed_requirements)