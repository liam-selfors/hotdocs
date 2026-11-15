import json
import os
import pprint
import re
import subprocess

import pytest

import review_packet_builder


# ---------------------------------------------------------------------------
# Unique detail tokens (so a bare status word can never satisfy an assertion)
# ---------------------------------------------------------------------------

LICENSE_PACKAGE = "gplonly-widget-9417"
LICENSE_FILE = "gen/foo/vendor/gplonly_widget_9417.py"
SECRET_FILE = "gen/foo/leaky_settings_5521.py"
CAPABILITY_ID = "P-FOO-WIDGET"
SPEC_ADDED_LINE = "the widget MUST also zorble the quux-4471 flange."
REGENERATED = "comp-foo"
SEALED = "comp-bar"
PINNED = "comp-baz"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git(repo, *args):
    cmd = [
        "git",
        "-c", "user.name=Review Packet Test",
        "-c", "user.email=review-packet-test@example.invalid",
        "-c", "commit.gpgsign=false",
        "-c", "init.defaultBranch=main",
    ] + list(args)
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    result = subprocess.run(
        cmd, cwd=str(repo), env=env, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return result.stdout.strip()


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, extra_lines=()):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [alice]",
    ]
    lines.extend(extra_lines)
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    lines.append("")
    lines.append("A synthetic fixture component.")
    lines.append("")
    return "\n".join(lines)


def _fake_tracker_source(report, log_path):
    return (
        "import copy\n"
        "import json\n"
        "\n"
        "_LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "_REPORT = " + pprint.pformat(report, width=100) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fn': 'check_readiness', 'changed_ids': None if changed_ids is None else list(changed_ids)}) + '\\n')\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _build_repo(tmp_path, report):
    repo = tmp_path / "repo"
    repo.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")

    # ---- base commit -----------------------------------------------------
    _write(
        repo / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _fake_tracker_source(report, log_path),
    )

    # comp-foo: the regenerated component
    _write(
        repo / "specs" / "components" / "foo" / "component.md",
        _component_md("comp-foo", "Foo", ["realizes: [" + CAPABILITY_ID + "]"]),
    )
    _write(
        repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — The widget MUST frob.\n",
    )
    _write(
        repo / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\nThe widget frobs.\n",
    )

    # comp-bar: will transition to sealed: true in the PR commit
    _write(
        repo / "specs" / "components" / "bar" / "component.md",
        _component_md("comp-bar", "Bar", ["sealed: false"]),
    )
    _write(
        repo / "specs" / "components" / "bar" / "requirements" / "R-BAR-001.md",
        "**R-BAR-001** — Bar MUST bar.\n",
    )
    _write(
        repo / "specs" / "components" / "bar" / "acceptance" / "AC-BAR-001.md",
        "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: compiled\n\nBar bars.\n",
    )

    # comp-baz: gains a pinned override in the PR commit
    _write(
        repo / "specs" / "components" / "baz" / "component.md",
        _component_md("comp-baz", "Baz"),
    )
    _write(
        repo / "specs" / "components" / "baz" / "requirements" / "R-BAZ-001.md",
        "**R-BAZ-001** — Baz MUST baz.\n",
    )
    _write(
        repo / "specs" / "components" / "baz" / "acceptance" / "AC-BAZ-001.md",
        "# AC-BAZ-001\n\nCovers: R-BAZ-001\nKind: compiled\n\nBaz bazzes.\n",
    )
    _write(repo / "gen" / "baz" / "baz.py", "def baz():\n    return 1\n")

    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base_sha = _git(repo, "rev-parse", "HEAD")

    # ---- PR commit on a feature branch -------------------------------------
    _git(repo, "checkout", "-q", "-b", "feature")

    req = repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
    req.write_text(
        req.read_text(encoding="utf-8") + "  Added in this PR: " + SPEC_ADDED_LINE + "\n",
        encoding="utf-8",
    )

    _write(
        repo / "specs" / "components" / "bar" / "component.md",
        _component_md("comp-bar", "Bar", ["sealed: true", "source_path: legacy/bar/"]),
    )

    _write(
        repo / "gen" / "baz" / ".overrides.json",
        json.dumps({"pinned": [{"path": "baz.py", "reason": "hand-tuned"}]}, indent=2) + "\n",
    )

    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "PR: change R-FOO-001, seal comp-bar, pin comp-baz")

    # Make the base discoverable under the common names a PR base is found by.
    _git(repo, "update-ref", "refs/remotes/origin/main", base_sha)
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    return repo, log_path


# ---------------------------------------------------------------------------
# Markdown section parsing (headings inside code fences are ignored)
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _sections(markdown):
    lines = markdown.splitlines()
    heads = []
    in_fence = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(line)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    out = []
    for k, (i, level, title) in enumerate(heads):
        end = len(lines)
        for (j, level2, _t) in heads[k + 1:]:
            if level2 <= level:
                end = j
                break
        out.append((title, level, "\n".join(lines[i + 1:end])))
    return out


def _section(markdown, predicate, label):
    matches = [body for (title, _lvl, body) in _sections(markdown) if predicate(title.lower())]
    assert matches, "no section heading found for %s in markdown:\n%s" % (label, markdown)
    return matches[0]


def _run_main(repo, capsys, monkeypatch):
    monkeypatch.chdir(repo)
    capsys.readouterr()
    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo)]
    )
    out = capsys.readouterr().out
    return rc, out


def _assert_tracker_called(log_path):
    assert log_path.exists(), "provenance-tracker fake's check_readiness was never invoked"
    records = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert any(r.get("fn") == "check_readiness" for r in records)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def _verification_report(mutation_score):
    return {
        "component_id": REGENERATED,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": mutation_score,
        "overall": "pass",
    }


def _flagged_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            REGENERATED: {
                "hit": True,
                "verification_report": _verification_report(0.92),
                "license_scan": {
                    "blocked": True,
                    "findings": [
                        {
                            "package": LICENSE_PACKAGE,
                            "license": "GPL-3.0-only",
                            "file": LICENSE_FILE,
                        }
                    ],
                },
                "secret_scan": {
                    "flagged": True,
                    "findings": [
                        {"file": SECRET_FILE, "line": 12, "kind": "aws-access-key"}
                    ],
                },
            }
        },
        "capabilities": {
            CAPABILITY_ID: {
                "hit": True,
                "capability_scenario_report": {
                    CAPABILITY_ID: {"overall": "pass", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [
            REGENERATED + ": license scan blocked",
            REGENERATED + ": secret scan flagged",
        ],
    }


def _clean_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            REGENERATED: {
                "hit": True,
                "verification_report": _verification_report(1.0),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_markdown_renders_real_detail_for_every_section(tmp_path, capsys, monkeypatch):
    repo, log_path = _build_repo(tmp_path, _flagged_report())

    rc, md = _run_main(repo, capsys, monkeypatch)

    assert rc == 0, "main returned %r; output:\n%s" % (rc, md)
    _assert_tracker_called(log_path)
    assert md.strip(), "nothing printed"

    # License scan: real flagged detail, not merely "blocked"
    lic = _section(md, lambda t: "license scan" in t, "License Scan")
    assert LICENSE_PACKAGE in lic or LICENSE_FILE in lic, (
        "License Scan section lacks the flagged entry's own detail:\n" + lic
    )

    # Secret scan: real flagged detail, not merely "flagged"
    sec = _section(md, lambda t: "secret scan" in t, "Secret Scan")
    assert SECRET_FILE in sec or "leaky_settings_5521" in sec, (
        "Secret Scan section lacks the flagged entry's own detail:\n" + sec
    )

    # Residual risk message
    rr = _section(md, lambda t: "residual risk" in t, "Residual Risk")
    assert "0.92" in rr or "92%" in rr, "Residual Risk section lacks the real message:\n" + rr

    # Capability scenario id
    cap = _section(md, lambda t: "capability scenario" in t, "Capability Scenarios")
    assert CAPABILITY_ID in cap, "Capability Scenarios section lacks the scenario id:\n" + cap

    # Exemption changes: sealed + pinned override component ids under their labels
    ex = _section(md, lambda t: "exemption change" in t, "Exemption Changes")
    s_idx = ex.find("**Sealed:**")
    p_idx = ex.find("**Pinned Overrides:**")
    assert s_idx != -1, "Exemption Changes lacks a **Sealed:** label:\n" + ex
    assert p_idx != -1, "Exemption Changes lacks a **Pinned Overrides:** label:\n" + ex
    sealed_seg = ex[s_idx:p_idx] if p_idx > s_idx else ex[s_idx:]
    pinned_seg = ex[p_idx:s_idx] if s_idx > p_idx else ex[p_idx:]
    assert SEALED in sealed_seg, "sealed component id missing under **Sealed:**:\n" + ex
    assert PINNED in pinned_seg, "pinned-override component id missing under **Pinned Overrides:**:\n" + ex

    # Spec diff text: the line this PR added under specs/
    diff = _section(md, lambda t: "diff" in t, "Spec Diff")
    assert SPEC_ADDED_LINE in diff, "Spec Diff section lacks the added spec line:\n" + diff

    # Changed requirement
    reqs = _section(
        md,
        lambda t: "requirement" in t and "verification" not in t,
        "Changed Requirements",
    )
    assert "R-FOO-001" in reqs, "Changed Requirements section lacks R-FOO-001:\n" + reqs

    # Regenerated component id
    regen = _section(md, lambda t: "regenerat" in t, "Regenerated Components")
    assert REGENERATED in regen, "Regenerated Components section lacks comp-foo:\n" + regen

    # Provenance hit status for the regenerated component (hit is True here)
    hit_word = re.compile(r"\b(true|hit|yes|reused|cached)\b", re.IGNORECASE)
    candidate_bodies = [
        body for (title, _lvl, body) in _sections(md)
        if "provenance" in title.lower() or "regenerat" in title.lower()
    ]
    assert candidate_bodies, "no provenance hit status section found:\n" + md
    assert any(
        REGENERATED in line and hit_word.search(line)
        for body in candidate_bodies
        for line in body.splitlines()
    ), "no line reports comp-foo's real provenance hit status:\n" + "\n---\n".join(candidate_bodies)

    # Verification results: real content for comp-foo
    ver = _section(md, lambda t: "verification result" in t, "Verification Results")
    assert REGENERATED in ver and "pass" in ver, "Verification Results lacks real content:\n" + ver


def test_markdown_renders_clean_placeholders_when_nothing_flagged(tmp_path, capsys, monkeypatch):
    repo, log_path = _build_repo(tmp_path, _clean_report())

    rc, md = _run_main(repo, capsys, monkeypatch)

    assert rc == 0, "main returned %r; output:\n%s" % (rc, md)
    _assert_tracker_called(log_path)

    lic = _section(md, lambda t: "license scan" in t, "License Scan")
    assert lic.strip(), "License Scan section renders no placeholder at all"
    assert REGENERATED not in lic, "License Scan lists an entry despite zero flags:\n" + lic

    sec = _section(md, lambda t: "secret scan" in t, "Secret Scan")
    assert sec.strip(), "Secret Scan section renders no placeholder at all"
    assert REGENERATED not in sec, "Secret Scan lists an entry despite zero flags:\n" + sec

    cap = _section(md, lambda t: "capability scenario" in t, "Capability Scenarios")
    assert cap.strip(), "Capability Scenarios section renders no placeholder at all"
    assert not re.search(r"\bP-[A-Z0-9]", cap), (
        "Capability Scenarios lists a capability despite zero intersecting ones:\n" + cap
    )

    ver = _section(md, lambda t: "verification result" in t, "Verification Results")
    assert REGENERATED in ver and "pass" in ver, (
        "Verification Results lacks real content for the regenerated component:\n" + ver
    )