import os
import subprocess

import review_packet_builder


def _run(args, cwd, env):
    subprocess.run(
        args, cwd=str(cwd), env=env, check=True, capture_output=True, text=True
    )


def test_spec_diff_contains_actual_diff_text_for_changed_component_md(tmp_path):
    repo_root = tmp_path
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test-author@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test-author@example.com"

    # A single-branch repo guarantees merge-base(HEAD, default-branch) == HEAD
    # regardless of how the default branch is resolved, since no other branch
    # exists for "default" to possibly name — this deterministically exercises
    # R-PACKET-001's documented fallback (diff the empty tree against HEAD).
    _run(["git", "init", "-b", "main"], repo_root, env)

    component_dir = repo_root / "specs" / "components" / "comp-foo"
    component_dir.mkdir(parents=True)
    component_md = component_dir / "component.md"

    component_md.write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [alice]\n"
        'last_ratified_commit: "0000000000000000000000000000000000000000"\n'
        "sealed: true\n"
        'source_path: "legacy/foo_v1.py"\n'
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "Original body text line ORIGINAL_MARKER_AAA111.\n"
    )

    _run(["git", "add", "-A"], repo_root, env)
    _run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", "add comp-foo component.md"],
        repo_root,
        env,
    )

    component_md.write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [alice]\n"
        'last_ratified_commit: "0000000000000000000000000000000000000000"\n'
        "sealed: true\n"
        'source_path: "legacy/foo_v1.py"\n'
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "Updated body text line UPDATED_MARKER_BBB222.\n"
    )

    _run(["git", "add", "-A"], repo_root, env)
    _run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", "update comp-foo component.md"],
        repo_root,
        env,
    )

    prov_tracker_dir = repo_root / "gen" / "provenance-tracker"
    prov_tracker_dir.mkdir(parents=True)
    (prov_tracker_dir / "provenance_tracker.py").write_text(
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {\n"
        "        \"scope\": \"blast-radius\",\n"
        "        \"ready\": True,\n"
        "        \"components\": {},\n"
        "        \"capabilities\": {},\n"
        "        \"not_ready_reasons\": [],\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    spec_diff = (
        packet.get("spec_diff")
        if isinstance(packet, dict)
        else getattr(packet, "spec_diff", None)
    )

    assert isinstance(spec_diff, str)
    assert "specs/components/comp-foo/component.md" in spec_diff
    assert "UPDATED_MARKER_BBB222" in spec_diff