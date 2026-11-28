# hotdocs-criterion: sha256:45d04e46763d9fd62957a41012c146c158fc43c2f6f55ff4f6eca5b032e315b2
import re
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STAND_IN_SOURCE = (
    "def _hit(cid):\n"
    "    return {\n"
    "        'hit': True,\n"
    "        'reason': None,\n"
    "        'verification_report': {\n"
    "            'component_id': cid,\n"
    "            'criteria': [],\n"
    "            'requirement_results': {},\n"
    "            'interface_drift': False,\n"
    "            'mutation_score': None,\n"
    "            'mutation_error': None,\n"
    "            'assets': [],\n"
    "            'drivers': [],\n"
    "            'overall': 'pass',\n"
    "        },\n"
    "        'license_scan': {'blocked': False, 'matches': []},\n"
    "        'secret_scan': {\n"
    "            'scope': 'full',\n"
    "            'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    "            'flagged': False,\n"
    "            'matches': [],\n"
    "            'allowed': [],\n"
    "            'unused_allowlist_entries': [],\n"
    "            'notified': False,\n"
    "            'notification_delivery_error': None,\n"
    "            'cache_hit': False,\n"
    "        },\n"
    "    }\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    components = {}\n"
    "    for cid in (changed_ids or []):\n"
    "        if str(cid).startswith('comp-'):\n"
    "            components[cid] = _hit(cid)\n"
    "    return {\n"
    "        'scope': 'blast-radius' if changed_ids is not None else 'whole-corpus',\n"
    "        'ready': True,\n"
    "        'components': components,\n"
    "        'capabilities': {},\n"
    "        'secret_scan': None,\n"
    "        'not_ready_reasons': [],\n"
    "    }\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


def git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo), check=True, capture_output=True, text=True,
    )


def write(repo, rel, text):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def commit(repo, msg):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", msg)


def component_md(cid, slug, sealed, body="A fixture component."):
    text = (
        "---\n"
        "id: " + cid + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
    )
    if sealed is True:
        text += "sealed: true\nsource_path: legacy/" + slug + "/\n"
    elif sealed is False:
        text += "sealed: false\n"
    text += "---\n\n# " + slug.capitalize() + "\n\n" + body + "\n"
    return text


def write_units(repo, slug, prefix):
    rid = "R-" + prefix + "-001"
    aid = "AC-" + prefix + "-001"
    write(repo, "specs/components/" + slug + "/requirements/" + rid + ".md",
          "# " + rid + "\n\n**" + rid + "** — The component MUST work.\n")
    write(repo, "specs/components/" + slug + "/acceptance/" + aid + ".md",
          "# " + aid + "\n\nCovers: " + rid + "\nKind: llm-judge\n\nIt works.\n")


def init_repo(repo):
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    write(repo, "gen/provenance-tracker/provenance_tracker.py", STAND_IN_SOURCE)
    write(repo, "README.md", "fixture\n")


def build_sealed_only_repo(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    commit(repo, "base")
    git(repo, "checkout", "-q", "-b", "feature")
    write(repo, "specs/components/foo/component.md", component_md("comp-foo", "foo", None))
    write_units(repo, "foo", "FOO")
    commit(repo, "add foo unsealed")
    write(repo, "specs/components/foo/component.md", component_md("comp-foo", "foo", True))
    commit(repo, "seal foo")
    return repo


def test_sealed_transition_appears_in_exemption_changes(tmp_path):
    repo = build_sealed_only_repo(tmp_path)
    packet = review_packet_builder.build_review_packet(["comp-foo"], repo)
    ex = field(packet, "exemption_changes")
    sealed = list(field(ex, "sealed"))
    assert "comp-foo" in sealed
    pinned = list(field(ex, "pinned_overrides"))
    assert "comp-foo" not in pinned


def _label_pos(section, pattern):
    m = re.search(r"^[#\s*\-_>|]*" + pattern, section, re.IGNORECASE | re.MULTILINE)
    return m.start() if m else None


def test_markdown_lists_sealed_and_empty_pinned_overrides(tmp_path, capsys):
    repo = build_sealed_only_repo(tmp_path)
    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=comp-foo", "--repo-root", str(repo)]
    )
    out = capsys.readouterr().out
    assert code == 0

    m = re.search(r"^([#*\s]*)exemption changes.*$", out, re.IGNORECASE | re.MULTILINE)
    assert m is not None, "no Exemption Changes section in markdown:\n" + out
    level = m.group(1).count("#")
    rest = out[m.end():]
    if level > 0:
        end = re.search(r"^#{1," + str(level) + r"}\s", rest, re.MULTILINE)
    else:
        end = None
    section = rest[: end.start()] if end else rest

    sealed_pos = _label_pos(section, r"sealed\b")
    pinned_pos = _label_pos(section, r"pinned[ _-]?overrides\b")
    assert sealed_pos is not None, "no Sealed label in section:\n" + section
    assert pinned_pos is not None, "no Pinned Overrides label in section:\n" + section

    if sealed_pos < pinned_pos:
        sealed_seg = section[sealed_pos:pinned_pos]
        pinned_seg = section[pinned_pos:]
    else:
        pinned_seg = section[pinned_pos:sealed_pos]
        sealed_seg = section[sealed_pos:]

    assert "comp-foo" in sealed_seg
    assert "comp-foo" not in pinned_seg
    assert "comp-" not in pinned_seg
    assert sealed_seg.strip() != pinned_seg.strip()


def test_non_transitions_and_deleted_override_excluded(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    write(repo, "gen/old/.overrides.json", '{"pinned": ["old.py"]}\n')
    commit(repo, "base with override")
    git(repo, "checkout", "-q", "-b", "feature")

    # Component A: sealed from birth, later edited, still sealed.
    write(repo, "specs/components/alpha/component.md",
          component_md("comp-alpha", "alpha", True))
    write_units(repo, "alpha", "ALPHA")
    # Component B: no sealed line at birth.
    write(repo, "specs/components/beta/component.md",
          component_md("comp-beta", "beta", None))
    write_units(repo, "beta", "BETA")
    commit(repo, "add alpha and beta")

    write(repo, "specs/components/alpha/component.md",
          component_md("comp-alpha", "alpha", True, body="Edited text, still sealed."))
    commit(repo, "edit alpha")
    write(repo, "specs/components/beta/component.md",
          component_md("comp-beta", "beta", False))
    commit(repo, "beta sealed false")

    (repo / "gen" / "old" / ".overrides.json").unlink()
    commit(repo, "delete old override")

    packet = review_packet_builder.build_review_packet(["comp-alpha", "comp-beta"], repo)
    ex = field(packet, "exemption_changes")
    sealed = list(field(ex, "sealed"))
    pinned = list(field(ex, "pinned_overrides"))
    assert "comp-alpha" not in sealed
    assert "comp-beta" not in sealed
    assert "comp-old" not in pinned
    assert "old" not in pinned