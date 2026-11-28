# hotdocs-criterion: sha256:1466dbbb8f30112dfdb41a85688723acd9db5482684a92ed79102da196fd75b5
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git_env():
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def git(root, *args):
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=True,
        env=_git_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout


def commit_all(root, message):
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-gpg-sign", "-m", message)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, sealed_line, body="Body text."):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: Component " + slug,
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
    ]
    if sealed_line is not None:
        lines.append(sealed_line)
    lines.append("source_path: legacy/" + slug + "/")
    lines.append("---")
    lines.append("")
    lines.append("# Component " + slug)
    lines.append("")
    lines.append(body)
    lines.append("")
    return "\n".join(lines)


def hit_entry(component_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": {
            "component_id": component_id,
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": None,
            "mutation_error": None,
            "assets": [],
            "drivers": [],
            "overall": "pass",
        },
        "license_scan": {"blocked": False},
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def write_tracker_standin(root, component_ids):
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {cid: hit_entry(cid) for cid in component_ids},
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [],
    }
    source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return " + repr(report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    write(root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


def init_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    git(root, "config", "commit.gpgsign", "false")


def build_sealed_only_repo(root):
    init_repo(root)
    write(root / "README.md", "fixture\n")
    write_tracker_standin(root, ["comp-foo"])
    commit_all(root, "initial")
    git(root, "checkout", "-q", "-b", "feature")
    comp = root / "specs" / "components" / "foo" / "component.md"
    write(comp, component_md("foo", None))
    commit_all(root, "add foo unsealed")
    write(comp, component_md("foo", "sealed: true"))
    commit_all(root, "seal foo")


def test_sealed_transition_appears_in_exemption_changes(tmp_path):
    root = tmp_path / "repo"
    build_sealed_only_repo(root)

    packet = review_packet_builder.build_review_packet(["comp-foo"], root)

    exemption = field(packet, "exemption_changes")
    sealed = list(field(exemption, "sealed"))
    pinned = list(field(exemption, "pinned_overrides"))
    assert "comp-foo" in sealed
    assert "comp-foo" not in pinned


def _section_lines(markdown):
    lines = markdown.splitlines()
    start = None
    level = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "exemption changes" in stripped.lower():
            start = i
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
            break
    assert start is not None, "no Exemption Changes section in markdown:\n" + markdown
    end = len(lines)
    if level is not None:
        for j in range(start + 1, len(lines)):
            s = lines[j].strip()
            if s.startswith("#"):
                lvl = len(s) - len(s.lstrip("#"))
                if lvl <= level:
                    end = j
                    break
    return lines[start + 1:end]


def test_markdown_renders_sealed_and_pinned_separately(tmp_path, capsys):
    root = tmp_path / "repo"
    build_sealed_only_repo(root)

    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=comp-foo", "--repo-root=" + str(root)]
    )
    out = capsys.readouterr().out
    assert code == 0

    section = _section_lines(out)
    sealed_idx = None
    pinned_idx = None
    for i, line in enumerate(section):
        low = line.lower()
        if pinned_idx is None and "pinned override" in low:
            pinned_idx = i
        elif sealed_idx is None and "sealed" in low and "pinned" not in low:
            sealed_idx = i
    assert sealed_idx is not None, "no Sealed subsection:\n" + "\n".join(section)
    assert pinned_idx is not None, "no Pinned Overrides subsection:\n" + "\n".join(section)

    if sealed_idx < pinned_idx:
        sealed_part = section[sealed_idx:pinned_idx]
        pinned_part = section[pinned_idx:]
    else:
        pinned_part = section[pinned_idx:sealed_idx]
        sealed_part = section[sealed_idx:]

    sealed_text = "\n".join(sealed_part)
    pinned_text = "\n".join(pinned_part)
    assert "comp-foo" in sealed_text, sealed_text
    assert "comp-foo" not in pinned_text, pinned_text
    assert "comp-" not in pinned_text, pinned_text


def test_non_transitions_and_deleted_override_excluded(tmp_path):
    root = tmp_path / "repo"
    init_repo(root)
    write(root / "README.md", "fixture\n")
    write_tracker_standin(root, ["comp-alpha", "comp-beta"])
    beta = root / "specs" / "components" / "beta" / "component.md"
    write(beta, component_md("beta", None))
    overrides = root / "gen" / "comp-old" / ".overrides.json"
    write(overrides, '{"pinned_files": ["old.py"]}\n')
    commit_all(root, "initial")

    git(root, "checkout", "-q", "-b", "feature")
    alpha = root / "specs" / "components" / "alpha" / "component.md"
    write(alpha, component_md("alpha", "sealed: true"))
    commit_all(root, "add alpha sealed from birth")

    write(alpha, component_md("alpha", "sealed: true", body="Edited body text."))
    commit_all(root, "edit alpha, still sealed")

    write(beta, component_md("beta", "sealed: false"))
    commit_all(root, "beta explicitly unsealed")

    overrides.unlink()
    commit_all(root, "delete comp-old overrides")

    packet = review_packet_builder.build_review_packet(["comp-alpha", "comp-beta"], root)

    exemption = field(packet, "exemption_changes")
    sealed = list(field(exemption, "sealed"))
    pinned = list(field(exemption, "pinned_overrides"))
    assert "comp-alpha" not in sealed
    assert "comp-beta" not in sealed
    assert "comp-old" not in pinned
    assert "old" not in pinned