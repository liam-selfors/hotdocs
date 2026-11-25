# hotdocs-criterion: sha256:b2d727dc56a6c9df0d25b4e2479d06d2da634e9108eef8cdb3fadee3102978d4
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    result = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo), env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def verification_report(component_id):
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


def secret_scan_result():
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


def license_scan_result():
    return {
        "blocked": False,
        "findings": [],
        "gate_version": "license_scanner@1.0.0",
        "cache_hit": False,
    }


def provenance_result(component_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(component_id),
        "license_scan": license_scan_result(),
        "secret_scan": secret_scan_result(),
    }


def write_tracker(repo, component_ids):
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {cid: provenance_result(cid) for cid in component_ids},
        "capabilities": {},
        "secret_scan": secret_scan_result(),
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
    write(repo / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


def component_md(component_id, title, sealed_line, source_line, extra=""):
    text = (
        "---\n"
        "id: " + component_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
    )
    if sealed_line:
        text += sealed_line + "\n"
    if source_line:
        text += source_line + "\n"
    text += "---\n\n# " + title + "\n\n" + extra + "\n"
    return text


def write_units(repo, slug, rid, acid):
    base = repo / "specs" / "components" / slug
    write(base / "requirements" / (rid + ".md"),
          "**" + rid + "** — The component MUST do its thing.\n")
    write(base / "acceptance" / (acid + ".md"),
          "# " + acid + "\n\nCovers: " + rid + "\nKind: llm-judge\n\nIt does its thing.\n")


def init_repo(repo):
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")


def build_sealed_only_repo(repo):
    init_repo(repo)
    write_tracker(repo, ["comp-foo"])
    write(repo / "README.md", "fixture\n")
    commit_all(repo, "initial")
    git(repo, "checkout", "-q", "-b", "feature")
    write_units(repo, "foo", "R-FOO-001", "AC-FOO-001")
    write(repo / "specs" / "components" / "foo" / "component.md",
          component_md("comp-foo", "Foo", None, None))
    commit_all(repo, "add foo unsealed")
    write(repo / "specs" / "components" / "foo" / "component.md",
          component_md("comp-foo", "Foo", "sealed: true", "source_path: legacy/foo/"))
    commit_all(repo, "seal foo")


def test_sealed_transition_in_library(tmp_path):
    repo = tmp_path / "repo"
    build_sealed_only_repo(repo)
    packet = review_packet_builder.build_review_packet(["comp-foo"], repo)
    exemptions = field(packet, "exemption_changes")
    sealed = list(field(exemptions, "sealed"))
    pinned = list(field(exemptions, "pinned_overrides"))
    assert "comp-foo" in sealed
    assert "comp-foo" not in pinned


def _section(lines):
    start = None
    for i, line in enumerate(lines):
        if "exemption changes" in line.lower():
            start = i
            break
    assert start is not None, "no Exemption Changes section in markdown output"
    heading = lines[start].lstrip()
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].lstrip()
        if stripped.startswith("#"):
            k = len(stripped) - len(stripped.lstrip("#"))
            if level == 0 or k <= level:
                end = j
                break
    return lines[start + 1:end]


def _label_index(lines, label):
    for i, line in enumerate(lines):
        cleaned = line.strip().lstrip("#*-_: ").lower()
        if cleaned.startswith(label):
            return i
    return None


def test_sealed_only_markdown_rendering(tmp_path, capsys):
    repo = tmp_path / "repo"
    build_sealed_only_repo(repo)
    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=comp-foo", "--repo-root", str(repo)]
    )
    out = capsys.readouterr().out
    assert code == 0
    section = _section(out.splitlines())
    sealed_i = _label_index(section, "sealed")
    pinned_i = _label_index(section, "pinned overrides")
    assert sealed_i is not None, "no Sealed list in Exemption Changes"
    assert pinned_i is not None, "no Pinned Overrides list in Exemption Changes"
    assert sealed_i != pinned_i
    if sealed_i < pinned_i:
        sealed_part = section[sealed_i:pinned_i]
        pinned_part = section[pinned_i:]
    else:
        pinned_part = section[pinned_i:sealed_i]
        sealed_part = section[sealed_i:]
    sealed_text = "\n".join(sealed_part)
    pinned_text = "\n".join(pinned_part)
    assert "comp-foo" in sealed_text
    assert "comp-foo" not in pinned_text
    assert sealed_text.replace("Sealed", "").replace("sealed", "") != \
        pinned_text.replace("Pinned Overrides", "").replace("pinned overrides", "")


def test_non_transitions_not_reported(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    write_tracker(repo, ["comp-alpha", "comp-beta"])
    write(repo / "README.md", "fixture\n")
    write(repo / "gen" / "old" / ".overrides.json", '{"pinned": ["old.py"]}\n')
    write(repo / "gen" / "old" / "old.py", "X = 1\n")
    commit_all(repo, "initial with old override")
    git(repo, "checkout", "-q", "-b", "feature")

    write_units(repo, "alpha", "R-ALPHA-001", "AC-ALPHA-001")
    write(repo / "specs" / "components" / "alpha" / "component.md",
          component_md("comp-alpha", "Alpha", "sealed: true", "source_path: legacy/alpha/"))
    write_units(repo, "beta", "R-BETA-001", "AC-BETA-001")
    write(repo / "specs" / "components" / "beta" / "component.md",
          component_md("comp-beta", "Beta", None, None))
    commit_all(repo, "add alpha sealed and beta unsealed")

    write(repo / "specs" / "components" / "alpha" / "component.md",
          component_md("comp-alpha", "Alpha", "sealed: true", "source_path: legacy/alpha/",
                       "Edited prose, still sealed."))
    write(repo / "specs" / "components" / "beta" / "component.md",
          component_md("comp-beta", "Beta", "sealed: false", None))
    (repo / "gen" / "old" / ".overrides.json").unlink()
    commit_all(repo, "edit alpha, beta sealed false, delete old override")

    packet = review_packet_builder.build_review_packet(["comp-alpha", "comp-beta"], repo)
    exemptions = field(packet, "exemption_changes")
    sealed = list(field(exemptions, "sealed"))
    pinned = list(field(exemptions, "pinned_overrides"))
    assert "comp-alpha" not in sealed
    assert "comp-beta" not in sealed
    assert "comp-old" not in pinned
    assert pinned == []