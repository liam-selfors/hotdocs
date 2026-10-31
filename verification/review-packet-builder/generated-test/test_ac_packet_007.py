import os
import re
import subprocess
from pathlib import Path

import review_packet_builder


FAKE_PROVENANCE_TRACKER_SRC = '''
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
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
'''


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "lselfors@gmail.com",
            "GIT_COMMITTER_NAME": "Test Author",
            "GIT_COMMITTER_EMAIL": "lselfors@gmail.com",
        }
    )
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        env=env,
    )


UNSEALED_COMPONENT_MD = """---
id: comp-foo
title: Foo Component
status: ratified
owners: [lselfors@gmail.com]
last_ratified_commit: "0000000000000000000000000000000000000000"
sealed: false
---

# Foo Component

A fixture component used to exercise a sealed-state transition.
"""

SEALED_COMPONENT_MD = """---
id: comp-foo
title: Foo Component
status: ratified
owners: [lselfors@gmail.com]
last_ratified_commit: "0000000000000000000000000000000000000000"
sealed: true
source_path: legacy/foo.py
---

# Foo Component

A fixture component used to exercise a sealed-state transition.
"""

REQUIREMENT_MD = """# R-FOO-001

R-FOO-001 - Foo must do the foo thing.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001

Given foo
When foo runs
Then foo succeeds
"""


def _build_fixture_repo(repo_root: Path) -> None:
    component_dir = repo_root / "specs" / "components" / "foo"
    (component_dir / "requirements").mkdir(parents=True)
    (component_dir / "acceptance").mkdir(parents=True)

    (component_dir / "component.md").write_text(UNSEALED_COMPONENT_MD)
    (component_dir / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (component_dir / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial: foo component (unsealed)")

    (component_dir / "component.md").write_text(SEALED_COMPONENT_MD)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "seal foo component")

    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True)
    (dep_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER_SRC)


def test_sealed_transition_appears_in_exemption_changes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture_repo(repo_root)

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    exemption_changes = _get(packet, "exemption_changes")
    sealed = _get(exemption_changes, "sealed", [])
    pinned_overrides = _get(exemption_changes, "pinned_overrides", [])

    assert "comp-foo" in sealed
    assert pinned_overrides == []


def _find_next_heading(text: str, start: int) -> int:
    match = re.search(r"\n#", text[start:])
    if match:
        return start + match.start()
    return len(text)


def test_markdown_rendering_separates_sealed_from_pinned_overrides(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture_repo(repo_root)

    argv = [
        "review-packet",
        "build",
        "--changed=comp-foo",
        f"--repo-root={repo_root}",
    ]

    try:
        exit_code = review_packet_builder.main(argv)
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 0

    output = capsys.readouterr().out

    exemption_idx = output.index("Exemption Changes")
    section_end = _find_next_heading(output, exemption_idx + len("Exemption Changes"))
    exemption_section = output[exemption_idx:section_end]

    sealed_label_idx = exemption_section.index("Sealed")
    pinned_label_idx = exemption_section.index("Pinned Overrides")

    if sealed_label_idx < pinned_label_idx:
        sealed_block = exemption_section[sealed_label_idx:pinned_label_idx]
        pinned_block = exemption_section[pinned_label_idx:]
    else:
        pinned_block = exemption_section[pinned_label_idx:sealed_label_idx]
        sealed_block = exemption_section[sealed_label_idx:]

    assert "comp-foo" in sealed_block
    assert "comp-foo" not in pinned_block