# hotdocs-criterion: sha256:d5fc73b84e87276180c8cb4741979f33e30cad2da9f739cc75a7f43e1fb1f215
import json
import os
import re
import subprocess
from pathlib import Path

import review_packet_builder


SPEC_ADDED_LINE = "The foo widget MUST also emit zq-unique-added-spec-line-4471."
LICENSE_PACKAGE = "gpl-widget-pkg-8812"
LICENSE_FILE = "gen/foo/vendor_widget.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo, *args):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo), env=env, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ).stdout


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component_md(cid, title, extra_lines):
    return (
        "---\n"
        "id: " + cid + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        + "".join(line + "\n" for line in extra_lines)
        + "---\n\n# " + title + "\n\nA fixture component.\n"
    )


def _verification_report(component_id, mutation_score):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": mutation_score,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "a" * 64,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "drivers": [],
        "overall": "pass",
    }


def _clean_secret_scan():
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


def _flagged_secret_scan():
    scan = _clean_secret_scan()
    scan["flagged"] = True
    scan["matches"] = [
        {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "a/b.py", "line": 3},
    ]
    return scan


def _clean_license_scan():
    return {
        "gate_version": "license_scanner@1.0.0",
        "blocked": False,
        "findings": [],
        "cache_hit": False,
    }


def _flagged_license_scan():
    return {
        "gate_version": "license_scanner@1.0.0",
        "blocked": True,
        "findings": [
            {"package": LICENSE_PACKAGE, "license": "GPL-3.0-only",
             "file": LICENSE_FILE, "blocked": True},
        ],
        "cache_hit": False,
    }


def _build_repo(repo, report, log_path):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")

    # Base state.
    _write(repo / "specs" / "components" / "foo" / "component.md",
           _component_md("comp-foo", "Foo", ["realizes: [P-FOO-CAP]"]))
    _write(repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
           "# R-FOO-001\n\n**R-FOO-001** — The foo widget MUST work.\n")
    _write(repo / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
           "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n")
    _write(repo / "specs" / "components" / "bar" / "component.md",
           _component_md("comp-bar", "Bar", ["sealed: false"]))
    _write(repo / "specs" / "components" / "baz" / "component.md",
           _component_md("comp-baz", "Baz", ["sealed: true", "source_path: legacy/baz/"]))
    _write(repo / "specs" / "product" / "P-FOO-CAP.md",
           "---\nid: P-FOO-CAP\ntitle: Foo Capability\nstatus: draft\n"
           "owners: [pipeline-team]\nrealized_by: [comp-foo]\n---\n\n# P-FOO-CAP\n\nA capability.\n")
    _write(repo / "gen" / "foo" / "foo.py", "X = 1\n")
    _write(repo / "gen" / "baz" / "baz.py", "Y = 2\n")

    tracker_src = (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness ' + json.dumps(list(changed_ids or [])) + '\\n')\n"
        "    return REPORT\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('last_requirement_failures ' + str(component_id) + '\\n')\n"
        "    return []\n"
    )
    _write(repo / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_src)

    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "update-ref", "refs/remotes/origin/main", base)

    # The PR: a spec line added, a real sealed transition, a real override addition.
    _git(repo, "checkout", "-q", "-b", "feature")
    req = repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
    req.write_text(req.read_text() + SPEC_ADDED_LINE + "\n")
    _write(repo / "specs" / "components" / "bar" / "component.md",
           _component_md("comp-bar", "Bar", ["sealed: true", "source_path: legacy/bar/"]))
    _write(repo / "gen" / "baz" / ".overrides.json",
           json.dumps({"files": ["baz.py"]}, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pr change")


_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _sections(md):
    out = []
    current = None
    in_fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
            in_fence = not in_fence
            if current is not None:
                current[1].append(line)
            continue
        m = None if in_fence else _HEADING.match(line)
        if m:
            current = (m.group(2).strip(), [])
            out.append(current)
        elif current is not None:
            current[1].append(line)
    return [(title, "\n".join(body)) for title, body in out]


def _section(md, *keywords):
    secs = _sections(md)
    for title, body in secs:
        if title.lower() == " ".join(keywords).lower():
            return body
    for title, body in secs:
        low = title.lower()
        if all(k.lower() in low for k in keywords):
            return body
    raise AssertionError("no section heading matching " + repr(keywords) + " in:\n" + md)


def _run(repo, capsys):
    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo)]
    )
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_markdown_renders_real_detail_in_every_section(tmp_path, capsys):
    repo = tmp_path / "repo"
    log_path = tmp_path / "tracker.log"
    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-foo", 0.92),
                "license_scan": _flagged_license_scan(),
                "secret_scan": _clean_secret_scan(),
            },
        },
        "capabilities": {
            "P-FOO-CAP": {
                "hit": True,
                "capability_scenario_report": {"P-FOO-CAP": {"overall": "pass", "scenarios": []}},
            },
        },
        "secret_scan": _flagged_secret_scan(),
        "not_ready_reasons": ["secret scan flagged: a/b.py:3"],
    }
    _build_repo(repo, report, log_path)

    rc, out, err = _run(repo, capsys)
    assert rc == 0, "stdout:\n" + out + "\nstderr:\n" + err
    assert log_path.is_file() and "check_readiness" in log_path.read_text()

    license_body = _section(out, "license scan")
    assert LICENSE_PACKAGE in license_body or LICENSE_FILE in license_body, license_body

    secret_body = _section(out, "secret scan")
    assert "a/b.py" in secret_body, secret_body

    residual_body = _section(out, "residual")
    assert "comp-foo" in residual_body, residual_body
    assert "0.92" in residual_body, residual_body

    cap_body = _section(out, "capability scenarios")
    cap_lines = [l for l in cap_body.splitlines() if l.strip().startswith("- ")]
    assert any("P-FOO-CAP" in l for l in cap_lines), cap_body

    exemption_body = _section(out, "exemption changes")
    assert "**Sealed:**" in exemption_body, exemption_body
    assert "**Pinned Overrides:**" in exemption_body, exemption_body
    s_idx = exemption_body.index("**Sealed:**")
    p_idx = exemption_body.index("**Pinned Overrides:**")
    if s_idx < p_idx:
        sealed_part = exemption_body[s_idx:p_idx]
        pinned_part = exemption_body[p_idx:]
    else:
        pinned_part = exemption_body[p_idx:s_idx]
        sealed_part = exemption_body[s_idx:]
    assert "comp-bar" in sealed_part, exemption_body
    assert "comp-baz" in pinned_part, exemption_body

    diff_body = _section(out, "spec diff")
    assert SPEC_ADDED_LINE in diff_body, diff_body

    changed_body = _section(out, "changed requirements")
    assert "R-FOO-001" in changed_body, changed_body

    regen_body = _section(out, "regenerated")
    assert "comp-foo" in regen_body, regen_body

    hit_body = _section(out, "provenance hit status")
    assert re.search(r"^\s*-\s*comp-foo:\s*hit=true\s*$", hit_body, re.MULTILINE), hit_body

    verif_body = _section(out, "verification results")
    assert any(l.strip().startswith("- comp-foo:") for l in verif_body.splitlines()), verif_body


def test_markdown_renders_clean_placeholders_when_nothing_flagged(tmp_path, capsys):
    repo = tmp_path / "repo"
    log_path = tmp_path / "tracker.log"
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-foo", 1.0),
                "license_scan": _clean_license_scan(),
                "secret_scan": _clean_secret_scan(),
            },
        },
        "capabilities": {},
        "secret_scan": _clean_secret_scan(),
        "not_ready_reasons": [],
    }
    _build_repo(repo, report, log_path)

    rc, out, err = _run(repo, capsys)
    assert rc == 0, "stdout:\n" + out + "\nstderr:\n" + err

    license_body = _section(out, "license scan")
    assert license_body.strip() != "", "License Scan section has no placeholder:\n" + out
    assert LICENSE_PACKAGE not in license_body

    secret_body = _section(out, "secret scan")
    assert secret_body.strip() != "", "Secret Scan section has no placeholder:\n" + out
    assert "a/b.py" not in secret_body

    cap_body = _section(out, "capability scenarios")
    assert cap_body.strip() != "", "Capability Scenarios section has no placeholder:\n" + out
    assert "P-FOO-CAP" not in cap_body

    verif_body = _section(out, "verification results")
    lines = [l.strip() for l in verif_body.splitlines()]
    entry = [l for l in lines if l.startswith("- comp-foo:")]
    assert entry, verif_body
    assert len(entry[0]) > len("- comp-foo:") + 1, verif_body