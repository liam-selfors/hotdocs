import review_packet_builder

import re
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=Test User",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _verification_report(component_id, rid, acid):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": acid, "covers": rid, "kind": "generated-test", "result": "pass"}
        ],
        "requirement_results": {rid: "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }


def _standin_source(component_specs):
    components = {}
    for component_id, rid, acid in component_specs:
        components[component_id] = {
            "hit": True,
            "verification_report": _verification_report(component_id, rid, acid),
            "license_scan": {"blocked": False, "findings": []},
            "secret_scan": {"flagged": False, "findings": []},
        }
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": components,
        "capabilities": {},
        "not_ready_reasons": [],
    }
    src = (
        "import copy\n"
        "\n"
        "REPORT = __REPORT__\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    return src.replace("__REPORT__", repr(report))


def _write_standin(repo, component_specs):
    _write(
        repo / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _standin_source(component_specs),
    )


def _component_md(component_id, title, sealed_line=None, body="Body text.\n"):
    lines = [
        "---",
        "id: %s" % component_id,
        "title: %s" % title,
        "status: draft",
        "owners: [test-owner]",
    ]
    if sealed_line is not None:
        lines.append(sealed_line)
        if sealed_line.strip() == "sealed: true":
            lines.append("source_path: legacy/%s/" % component_id[len("comp-"):])
    lines.append("---")
    lines.append("")
    lines.append("# %s" % title)
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def _write_component(repo, slug, component_id, title, rid, acid, sealed_line=None, body="Body text.\n"):
    base = repo / "specs" / "components" / slug
    _write(base / "component.md", _component_md(component_id, title, sealed_line, body))
    _write(
        base / "requirements" / ("%s.md" % rid),
        "**%s** -- %s MUST do its thing.\n" % (rid, title),
    )
    _write(
        base / "acceptance" / ("%s.md" % acid),
        "# %s\n\nCovers: %s\nKind: generated-test\n\n```gherkin\nGiven x\nWhen y\nThen z\n```\n"
        % (acid, rid),
    )


def _init_repo(repo):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")


def _make_foo_repo(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_standin(repo, [("comp-foo", "R-FOO-001", "AC-FOO-001")])
    # First commit: no sealed line at all.
    _write_component(repo, "foo", "comp-foo", "Foo", "R-FOO-001", "AC-FOO-001", sealed_line=None)
    _commit(repo, "add comp-foo unsealed")
    _git(repo, "checkout", "-q", "-b", "feature")
    # Second real commit: sealed: true.
    _write_component(repo, "foo", "comp-foo", "Foo", "R-FOO-001", "AC-FOO-001", sealed_line="sealed: true")
    _commit(repo, "seal comp-foo")
    return repo


def _heading_level(line):
    if not line.startswith("#"):
        return None
    return len(line) - len(line.lstrip("#"))


_PINNED_RE = re.compile(r"pinned[ _-]?overrides?", re.IGNORECASE)


def _split_exemption_section(md):
    lines = md.splitlines()
    start = None
    for i, line in enumerate(lines):
        if "exemption changes" in line.lower() or "exemption_changes" in line.lower():
            start = i
            break
    assert start is not None, "markdown has no Exemption Changes section:\n" + md

    level = _heading_level(lines[start])
    end = len(lines)
    if level is not None:
        for j in range(start + 1, len(lines)):
            lvl = _heading_level(lines[j])
            if lvl is not None and lvl <= level:
                end = j
                break
    section = lines[start + 1:end]

    sealed_idx = None
    pinned_idx = None
    for k, line in enumerate(section):
        low = line.lower()
        has_pinned = bool(_PINNED_RE.search(line))
        has_sealed = "sealed" in low
        if sealed_idx is None and has_sealed and not has_pinned:
            sealed_idx = k
        if pinned_idx is None and has_pinned and not has_sealed:
            pinned_idx = k
    assert sealed_idx is not None, "no Sealed label in Exemption Changes:\n" + "\n".join(section)
    assert pinned_idx is not None, "no Pinned Overrides label in Exemption Changes:\n" + "\n".join(section)

    def _part(idx, other_idx):
        stop = len(section)
        if other_idx > idx:
            stop = other_idx
        for m in range(idx + 1, stop):
            if section[m].startswith("#"):
                stop = m
                break
        return section[idx:stop]

    sealed_part = _part(sealed_idx, pinned_idx)
    pinned_part = _part(pinned_idx, sealed_idx)
    return sealed_part, pinned_part


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_sealed_transition_reported_in_exemption_changes(tmp_path):
    repo = _make_foo_repo(tmp_path)

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo)

    exemption = field(packet, "exemption_changes")
    sealed = list(field(exemption, "sealed"))
    assert "comp-foo" in sealed


def test_markdown_lists_sealed_under_sealed_and_pinned_overrides_empty(tmp_path, capsys):
    repo = _make_foo_repo(tmp_path)
    capsys.readouterr()

    argv = [
        "review-packet", "build",
        "--changed=comp-foo",
        "--repo-root", str(repo),
    ]
    try:
        rc = review_packet_builder.main(argv)
    except SystemExit as exc:
        rc = exc.code
    out = capsys.readouterr().out

    assert rc in (0, None), "main exited %r; output:\n%s" % (rc, out)

    sealed_part, pinned_part = _split_exemption_section(out)
    sealed_text = "\n".join(sealed_part)
    pinned_text = "\n".join(pinned_part)

    assert "comp-foo" in sealed_text, (
        "sealed component not listed under Sealed:\n" + sealed_text
    )
    assert "comp-foo" not in pinned_text, (
        "sealed component wrongly listed under Pinned Overrides:\n" + pinned_text
    )
    assert "comp-" not in pinned_text, (
        "Pinned Overrides should render as empty:\n" + pinned_text
    )
    # The two lists must never be rendered identically.
    assert [l.strip() for l in sealed_part[1:]] != [l.strip() for l in pinned_part[1:]] \
        or sealed_part[0].lower().replace("sealed", "") != pinned_part[0].lower(), (
        "Sealed and Pinned Overrides rendered identically"
    )


def test_non_transitions_and_deleted_override_not_reported(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_standin(
        repo,
        [
            ("comp-alpha", "R-ALPHA-001", "AC-ALPHA-001"),
            ("comp-beta", "R-BETA-001", "AC-BETA-001"),
        ],
    )
    # alpha: sealed from birth.
    _write_component(
        repo, "alpha", "comp-alpha", "Alpha", "R-ALPHA-001", "AC-ALPHA-001",
        sealed_line="sealed: true",
    )
    # beta: first committed with no sealed line.
    _write_component(
        repo, "beta", "comp-beta", "Beta", "R-BETA-001", "AC-BETA-001",
        sealed_line=None,
    )
    # override file for comp-old present at the PR diff-base.
    _write(
        repo / "gen" / "old" / ".overrides.json",
        '{"pinned": ["old.py"]}\n',
    )
    _write(repo / "gen" / "old" / "old.py", "VALUE = 1\n")
    _commit(repo, "base state")

    _git(repo, "checkout", "-q", "-b", "feature")

    # alpha edited, still sealed: true.
    _write_component(
        repo, "alpha", "comp-alpha", "Alpha", "R-ALPHA-001", "AC-ALPHA-001",
        sealed_line="sealed: true", body="Edited body text, still sealed.\n",
    )
    _commit(repo, "edit comp-alpha")

    # beta changed to sealed: false.
    _write_component(
        repo, "beta", "comp-beta", "Beta", "R-BETA-001", "AC-BETA-001",
        sealed_line="sealed: false",
    )
    _commit(repo, "comp-beta sealed: false")

    # override file deleted in this PR.
    _git(repo, "rm", "-q", "gen/old/.overrides.json")
    _git(repo, "commit", "-q", "-m", "delete comp-old overrides")

    packet = review_packet_builder.build_review_packet(["comp-alpha", "comp-beta"], repo)

    exemption = field(packet, "exemption_changes")
    sealed = list(field(exemption, "sealed"))
    pinned = list(field(exemption, "pinned_overrides"))

    assert "comp-alpha" not in sealed
    assert "comp-beta" not in sealed
    assert "comp-old" not in pinned