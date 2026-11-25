# hotdocs-criterion: sha256:b2d727dc56a6c9df0d25b4e2479d06d2da634e9108eef8cdb3fadee3102978d4
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"] + list(args),
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component_md(component_id, title, sealed_line):
    text = "---\n"
    text += "id: " + component_id + "\n"
    text += "title: " + title + "\n"
    text += "status: draft\n"
    text += "owners: [pipeline-team]\n"
    text += "depends_on: []\n"
    if sealed_line is not None:
        text += sealed_line + "\n"
        if sealed_line.strip() == "sealed: true":
            text += "source_path: legacy/" + component_id[len("comp-"):] + "/\n"
    text += "---\n\n# " + title + "\n\nA fixture component.\n"
    return text


def _verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _verify_report(component_ids):
    components = {}
    for cid in component_ids:
        components[cid] = {
            "hit": True,
            "reason": None,
            "verification_report": _verification_report(cid),
            "license_scan": {"blocked": False, "matches": []},
            "secret_scan": _secret_scan(),
        }
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": components,
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [],
    }


def _write_tracker_standin(repo, component_ids):
    report = _verify_report(component_ids)
    source = ""
    source += "import copy\n\n"
    source += "REPORT = " + repr(report) + "\n\n\n"
    source += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    source += "    return copy.deepcopy(REPORT)\n\n\n"
    source += "def last_requirement_failures(component_id, repo_root):\n"
    source += "    return []\n"
    _write(repo / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


def _init_repo(repo):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")


def _build_sealed_only_repo(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_tracker_standin(repo, ["comp-foo"])
    _write(repo / "README.md", "fixture\n")
    _write(
        repo / "specs" / "components" / "foo" / "component.md",
        _component_md("comp-foo", "Foo", None),
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "add comp-foo unsealed")
    _git(repo, "checkout", "-b", "feature")
    _write(
        repo / "specs" / "components" / "foo" / "component.md",
        _component_md("comp-foo", "Foo", "sealed: true"),
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seal comp-foo")
    return repo


def _exemption_changes(packet):
    return field(packet, "exemption_changes")


def test_sealed_transition_appears_in_exemption_changes(tmp_path):
    repo = _build_sealed_only_repo(tmp_path)
    packet = review_packet_builder.build_review_packet(["comp-foo"], repo)
    ex = _exemption_changes(packet)
    sealed = list(field(ex, "sealed"))
    pinned = list(field(ex, "pinned_overrides"))
    assert "comp-foo" in sealed
    assert "comp-foo" not in pinned


def _heading_level(line):
    stripped = line.lstrip()
    if not stripped.startswith("#"):
        return None
    level = len(stripped) - len(stripped.lstrip("#"))
    return level


def _exemption_section(text):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if "exemption changes" in line.lower():
            start = i
            break
    assert start is not None, "no Exemption Changes section in markdown:\n" + text
    level = _heading_level(lines[start])
    end = len(lines)
    if level is not None:
        for j in range(start + 1, len(lines)):
            lv = _heading_level(lines[j])
            if lv is not None and lv <= level:
                end = j
                break
    return lines[start + 1:end]


def test_markdown_lists_sealed_not_pinned(tmp_path, capsys):
    repo = _build_sealed_only_repo(tmp_path)
    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=comp-foo", "--repo-root=" + str(repo)]
    )
    out = capsys.readouterr().out
    assert code == 0
    section = _exemption_section(out)

    sealed_idx = None
    pinned_idx = None
    for i, line in enumerate(section):
        low = line.lower()
        if pinned_idx is None and "pinned" in low:
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

    sealed_body = "\n".join(sealed_part[1:]).strip() + sealed_part[0].lower().split("sealed", 1)[-1]
    pinned_body = "\n".join(pinned_part[1:]).strip() + pinned_part[0].lower().split("pinned", 1)[-1]
    assert sealed_body != pinned_body


def test_non_transitions_and_deleted_override_excluded(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_tracker_standin(repo, ["comp-alpha", "comp-beta"])
    _write(repo / "README.md", "fixture\n")
    _write(
        repo / "specs" / "components" / "alpha" / "component.md",
        _component_md("comp-alpha", "Alpha", "sealed: true"),
    )
    _write(
        repo / "specs" / "components" / "beta" / "component.md",
        _component_md("comp-beta", "Beta", None),
    )
    _write(repo / "gen" / "old" / ".overrides.json", "{}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base state")

    _git(repo, "checkout", "-b", "feature")
    _write(
        repo / "specs" / "components" / "alpha" / "component.md",
        _component_md("comp-alpha", "Alpha Edited", "sealed: true"),
    )
    _write(
        repo / "specs" / "components" / "beta" / "component.md",
        _component_md("comp-beta", "Beta", "sealed: false"),
    )
    _git(repo, "rm", "-q", "gen/old/.overrides.json")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "edit alpha, beta sealed false, drop override")

    packet = review_packet_builder.build_review_packet(["comp-alpha", "comp-beta"], repo)
    ex = _exemption_changes(packet)
    sealed = list(field(ex, "sealed"))
    pinned = list(field(ex, "pinned_overrides"))
    assert "comp-alpha" not in sealed
    assert "comp-beta" not in sealed
    assert "comp-old" not in pinned
    assert "comp-comp-old" not in pinned
    assert "old" not in pinned