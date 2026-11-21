# hotdocs-criterion: sha256:195f2f5aa34d740e373ec671c683d5eb0b926af953708a3d4ee1dbe73b26342f
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


_VERIFICATION_REPORT = {
    "component_id": "comp-placeholder",
    "criteria": [],
    "requirement_results": {},
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

_PROVENANCE_CHECK_RESULT = {
    "hit": True,
    "reason": None,
    "verification_report": _VERIFICATION_REPORT,
    "license_scan": {"blocked": False, "findings": []},
    "secret_scan": {"flagged": False, "findings": []},
}

STANDIN_SOURCE = (
    "import copy\n"
    "\n"
    "_RESULT = " + repr(_PROVENANCE_CHECK_RESULT) + "\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    components = {}\n"
    "    for cid in (changed_ids or []):\n"
    "        if str(cid).startswith(" + repr("comp-") + "):\n"
    "            entry = copy.deepcopy(_RESULT)\n"
    "            entry[" + repr("verification_report") + "][" + repr("component_id") + "] = cid\n"
    "            components[cid] = entry\n"
    "    return {\n"
    "        " + repr("scope") + ": (" + repr("blast-radius") + " if changed_ids is not None else " + repr("whole-corpus") + "),\n"
    "        " + repr("ready") + ": True,\n"
    "        " + repr("components") + ": components,\n"
    "        " + repr("capabilities") + ": {},\n"
    "        " + repr("not_ready_reasons") + ": [],\n"
    "    }\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


def _git(repo, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"] + list(args),
        cwd=str(repo),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _init_repo(repo, extra_base_files=None):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _write(repo / "README.md", "fixture repo\n")
    _write(repo / "gen" / "provenance-tracker" / "provenance_tracker.py", STANDIN_SOURCE)
    for rel, text in (extra_base_files or {}).items():
        _write(repo / rel, text)
    _commit(repo, "base")
    _git(repo, "checkout", "-q", "-b", "feature")


def _component_md(slug, sealed_line, body):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + slug.capitalize() + " component",
        "status: draft",
        "owners: [team-a]",
    ]
    if sealed_line is not None:
        lines.append(sealed_line)
        if sealed_line.strip() == "sealed: true":
            lines.append("source_path: legacy/" + slug + "/")
    lines.append("depends_on: []")
    lines.append("---")
    lines.append("")
    lines.append("# " + slug.capitalize())
    lines.append("")
    lines.append(body)
    lines.append("")
    return "\n".join(lines)


def _write_component(repo, slug, sealed_line, body):
    base = repo / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, sealed_line, body))
    rid = "R-" + slug.upper() + "-001"
    acid = "AC-" + slug.upper() + "-001"
    _write(base / "requirements" / (rid + ".md"), "**" + rid + "** — The component MUST do its job.\n")
    _write(
        base / "acceptance" / (acid + ".md"),
        "# " + acid + "\n\nCovers: " + rid + "\nKind: llm-judge\n\nThe component does its job.\n",
    )


def _build_sealed_only_repo(repo):
    _init_repo(repo)
    _write_component(repo, "foo", None, "Initial foo body.")
    _commit(repo, "add foo unsealed")
    _write_component(repo, "foo", "sealed: true", "Initial foo body.")
    _commit(repo, "seal foo")


def test_sealed_transition_appears_in_exemption_changes(tmp_path):
    repo = tmp_path / "repo"
    _build_sealed_only_repo(repo)

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo)
    exemptions = field(packet, "exemption_changes")
    sealed = list(field(exemptions, "sealed"))
    pinned = list(field(exemptions, "pinned_overrides"))

    assert "comp-foo" in sealed
    assert "comp-foo" not in pinned


def _section(lines, title):
    start = None
    level = 0
    for i, line in enumerate(lines):
        if title.lower() in line.lower():
            start = i
            stripped = line.lstrip()
            level = len(stripped) - len(stripped.lstrip("#"))
            break
    assert start is not None, "no " + repr(title) + " section in markdown"
    end = len(lines)
    if level > 0:
        for j in range(start + 1, len(lines)):
            s = lines[j].lstrip()
            hashes = len(s) - len(s.lstrip("#"))
            if 0 < hashes <= level and s[hashes:hashes + 1] in (" ", ""):
                end = j
                break
    return lines[start + 1:end]


def _label(line):
    return line.strip().lstrip("#*-_ \t").lower()


def test_markdown_lists_sealed_under_sealed_and_pinned_overrides_empty(tmp_path, capsys):
    repo = tmp_path / "repo"
    _build_sealed_only_repo(repo)
    capsys.readouterr()

    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=comp-foo", "--repo-root=" + str(repo)]
    )
    out = capsys.readouterr().out
    assert code == 0

    body = _section(out.splitlines(), "Exemption Changes")
    sealed_idx = None
    pinned_idx = None
    for i, line in enumerate(body):
        lab = _label(line)
        if sealed_idx is None and lab.startswith("sealed"):
            sealed_idx = i
        if pinned_idx is None and lab.startswith("pinned overrides"):
            pinned_idx = i
    assert sealed_idx is not None, "no Sealed list in Exemption Changes section"
    assert pinned_idx is not None, "no Pinned Overrides list in Exemption Changes section"

    if sealed_idx < pinned_idx:
        sealed_part = "\n".join(body[sealed_idx:pinned_idx])
        pinned_part = "\n".join(body[pinned_idx:])
    else:
        pinned_part = "\n".join(body[pinned_idx:sealed_idx])
        sealed_part = "\n".join(body[sealed_idx:])

    assert "comp-foo" in sealed_part
    assert "comp-foo" not in pinned_part
    assert "comp-" not in pinned_part


def test_non_transitions_and_deleted_override_are_excluded(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(
        repo,
        extra_base_files={"gen/comp-old/.overrides.json": "{}\n"},
    )
    # Sealed from birth, later edited (still sealed).
    _write_component(repo, "bar", "sealed: true", "Initial bar body.")
    # No sealed line at first commit.
    _write_component(repo, "baz", None, "Initial baz body.")
    _commit(repo, "add bar sealed and baz unsealed")

    _write_component(repo, "bar", "sealed: true", "Edited bar body.")
    _write_component(repo, "baz", "sealed: false", "Initial baz body.")
    (repo / "gen" / "comp-old" / ".overrides.json").unlink()
    _commit(repo, "edit bar, set baz sealed false, delete comp-old overrides")

    packet = review_packet_builder.build_review_packet(["comp-bar", "comp-baz"], repo)
    exemptions = field(packet, "exemption_changes")
    sealed = list(field(exemptions, "sealed"))
    pinned = list(field(exemptions, "pinned_overrides"))

    assert "comp-bar" not in sealed
    assert "comp-baz" not in sealed
    assert "comp-old" not in pinned