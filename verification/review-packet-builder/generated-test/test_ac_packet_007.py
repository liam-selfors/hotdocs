# hotdocs-criterion: sha256:4b420363588bca03ed5aa5e0e1bd9ce885ea1e97aab5c8b6c42d91a813c41715
import os
import re
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"] + list(args),
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def write(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def component_md(component_id, title, sealed_line, source_path):
    text = "---\n"
    text += "id: " + component_id + "\n"
    text += "title: " + title + "\n"
    text += "status: draft\n"
    text += "owners: [alice]\n"
    if sealed_line is not None:
        text += sealed_line + "\n"
    if source_path is not None:
        text += "source_path: " + source_path + "\n"
    text += "---\n\n# " + title + "\n\nA fixture component.\n"
    return text


def add_unit_files(repo, slug, rid, acid):
    write(repo, "specs/components/" + slug + "/requirements/" + rid + ".md",
          "**" + rid + "** - The component MUST do its thing.\n")
    write(repo, "specs/components/" + slug + "/acceptance/" + acid + ".md",
          "# " + acid + "\n\nCovers: " + rid + "\nKind: generated-test\n")


def provenance_check_result(component_id):
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": None,
            "mutation_error": None,
            "overall": "pass",
        },
        "license_scan": {"blocked": False, "matches": []},
        "secret_scan": {"flagged": False, "findings": []},
    }


def write_stand_in(repo, component_ids):
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {cid: provenance_check_result(cid) for cid in component_ids},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    src = "import copy\n\n"
    src += "REPORT = " + repr(report) + "\n\n\n"
    src += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    src += "    return copy.deepcopy(REPORT)\n\n\n"
    src += "def last_requirement_failures(component_id, repo_root):\n"
    src += "    return []\n"
    write(repo, "gen/provenance-tracker/provenance_tracker.py", src)


def init_repo(repo, component_ids):
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    write(repo, "README.md", "fixture\n")
    write_stand_in(repo, component_ids)
    commit_all(repo, "initial")


def build_sealed_only_repo(tmp_path):
    repo = tmp_path / "repo_sealed"
    init_repo(repo, ["comp-foo"])
    git(repo, "checkout", "-q", "-b", "feature")
    write(repo, "specs/components/foo/component.md",
          component_md("comp-foo", "Foo", None, None))
    add_unit_files(repo, "foo", "R-FOO-001", "AC-FOO-001")
    commit_all(repo, "add foo unsealed")
    write(repo, "specs/components/foo/component.md",
          component_md("comp-foo", "Foo", "sealed: true", "legacy/foo/"))
    commit_all(repo, "seal foo")
    return repo


def run_main(argv):
    try:
        rc = review_packet_builder.main(argv)
    except SystemExit as exc:
        rc = exc.code
    return 0 if rc is None else rc


def test_sealed_transition_appears_in_exemption_changes(tmp_path):
    repo = build_sealed_only_repo(tmp_path)
    packet = review_packet_builder.build_review_packet(["comp-foo"], Path(repo))
    exemptions = field(packet, "exemption_changes")
    sealed = list(field(exemptions, "sealed"))
    pinned = list(field(exemptions, "pinned_overrides"))
    assert "comp-foo" in sealed
    assert "comp-foo" not in pinned


def _exemption_section(out):
    lines = out.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.search(r"exemption\s+changes", line, re.I):
            start = i
            break
    assert start is not None, "no Exemption Changes section in:\n" + out
    m = re.match(r"^\s*(#+)\s", lines[start])
    level = len(m.group(1)) if m else None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        hm = re.match(r"^\s*(#+)\s+(.*)$", lines[j])
        if not hm:
            continue
        if re.search(r"sealed|pinned", hm.group(2), re.I):
            continue
        if level is None or len(hm.group(1)) <= level:
            end = j
            break
    return lines[start + 1:end]


def test_markdown_lists_sealed_under_sealed_and_pinned_overrides_empty(tmp_path, capsys):
    repo = build_sealed_only_repo(tmp_path)
    capsys.readouterr()
    rc = run_main(["review-packet", "build", "--changed=comp-foo", "--repo-root=" + str(repo)])
    out = capsys.readouterr().out
    assert rc == 0, out

    section = _exemption_section(out)
    sealed_re = re.compile(r"^[\s#*_>|\-]*sealed\b", re.I)
    pinned_re = re.compile(r"^[\s#*_>|\-]*pinned[\s_\-]*overrides?\b", re.I)
    s_idx = next((i for i, l in enumerate(section) if sealed_re.match(l)), None)
    p_idx = next((i for i, l in enumerate(section) if pinned_re.match(l)), None)
    assert s_idx is not None, "no Sealed label in Exemption Changes:\n" + "\n".join(section)
    assert p_idx is not None, "no Pinned Overrides label in Exemption Changes:\n" + "\n".join(section)
    if s_idx < p_idx:
        sealed_part = section[s_idx:p_idx]
        pinned_part = section[p_idx:]
    else:
        pinned_part = section[p_idx:s_idx]
        sealed_part = section[s_idx:]
    assert "comp-foo" in "\n".join(sealed_part), "\n".join(section)
    assert "comp-foo" not in "\n".join(pinned_part), "\n".join(section)


def test_non_transitions_and_deleted_override_are_not_exemption_changes(tmp_path):
    repo = tmp_path / "repo_negative"
    init_repo(repo, ["comp-alpha", "comp-beta"])
    # Override present at the PR diff-base (main).
    write(repo, "gen/comp-old/.overrides.json", '{"pinned": ["old.py"]}\n')
    commit_all(repo, "add comp-old override")
    git(repo, "checkout", "-q", "-b", "feature")

    # comp-alpha: sealed from birth, later edited, still sealed.
    write(repo, "specs/components/alpha/component.md",
          component_md("comp-alpha", "Alpha", "sealed: true", "legacy/alpha/"))
    add_unit_files(repo, "alpha", "R-ALPHA-001", "AC-ALPHA-001")
    commit_all(repo, "add alpha sealed")
    write(repo, "specs/components/alpha/component.md",
          component_md("comp-alpha", "Alpha Edited", "sealed: true", "legacy/alpha/"))
    commit_all(repo, "edit alpha")

    # comp-beta: no sealed line at first, later sealed: false.
    write(repo, "specs/components/beta/component.md",
          component_md("comp-beta", "Beta", None, None))
    add_unit_files(repo, "beta", "R-BETA-001", "AC-BETA-001")
    commit_all(repo, "add beta")
    write(repo, "specs/components/beta/component.md",
          component_md("comp-beta", "Beta", "sealed: false", None))
    commit_all(repo, "beta sealed false")

    # Delete the override in this PR.
    git(repo, "rm", "-q", "gen/comp-old/.overrides.json")
    git(repo, "commit", "-q", "-m", "remove comp-old override")

    packet = review_packet_builder.build_review_packet(["comp-alpha", "comp-beta"], Path(repo))
    exemptions = field(packet, "exemption_changes")
    sealed = list(field(exemptions, "sealed"))
    pinned = list(field(exemptions, "pinned_overrides"))
    assert "comp-alpha" not in sealed
    assert "comp-beta" not in sealed
    assert "comp-old" not in pinned
    assert "comp-comp-old" not in pinned