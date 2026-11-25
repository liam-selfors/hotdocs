# hotdocs-criterion: sha256:89086513bc88ef99e04b14ac36a1b306fb728e39b9aca44a2dc4a6e59ae46f9b
import re
import subprocess
from pathlib import Path

import review_packet_builder


# ---------------------------------------------------------------- helpers

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root), check=True, capture_output=True, text=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def verification_report(component_id, mutation_score):
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
                    "adapter_sha256": "sha256:abc", "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": "pass",
    }


def secret_scan_result(matches):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": bool(matches),
        "matches": matches,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def license_scan_result(blocked):
    findings = []
    if blocked:
        findings = [{"file": "gen/foo/vendored_evil.py", "package": "evil-gpl-lib",
                     "license": "GPL-3.0-only", "similarity": 0.97}]
    return {
        "gate_version": "license_scanner@1.0.0",
        "blocked": blocked,
        "findings": findings,
        "cache_hit": False,
    }


def component_md(cid, title, extra_lines):
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


def write_fake_tracker(repo_root, report, log_path):
    source = (
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness ' + repr(changed_ids) + '\\n')\n"
        "    return REPORT\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


ADDED_SPEC_LINE = "The foo widget MUST reject a negative quux count with exit 3."


def build_repo(tmp_path, report, with_pr_changes):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"
    git(repo_root, "init")
    git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")

    write_fake_tracker(repo_root, report, log_path)

    foo = repo_root / "specs" / "components" / "foo"
    write(foo / "component.md",
          component_md("comp-foo", "Foo", ["realizes: [P-FOO-CAP]"]))
    write(foo / "requirements" / "R-FOO-001.md",
          "# R-FOO-001\n\n**R-FOO-001** — The foo widget MUST frobnicate.\n")
    write(foo / "acceptance" / "AC-FOO-001.md",
          "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n")

    sealy = repo_root / "specs" / "components" / "sealy"
    write(sealy / "component.md",
          component_md("comp-sealy", "Sealy", ["sealed: false"]))
    write(sealy / "requirements" / "R-SEALY-001.md",
          "# R-SEALY-001\n\n**R-SEALY-001** — Sealy MUST exist.\n")
    write(sealy / "acceptance" / "AC-SEALY-001.md",
          "# AC-SEALY-001\n\nCovers: R-SEALY-001\nKind: compiled\n")

    pinny = repo_root / "specs" / "components" / "pinny"
    write(pinny / "component.md",
          component_md("comp-pinny", "Pinny", ["sealed: true", "source_path: legacy/pinny/"]))
    write(pinny / "requirements" / "R-PINNY-001.md",
          "# R-PINNY-001\n\n**R-PINNY-001** — Pinny MUST exist.\n")
    write(pinny / "acceptance" / "AC-PINNY-001.md",
          "# AC-PINNY-001\n\nCovers: R-PINNY-001\nKind: compiled\n")
    write(repo_root / "gen" / "pinny" / "pinny.py", "VALUE = 1\n")

    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "base")
    git(repo_root, "checkout", "-b", "pr-branch")

    if with_pr_changes:
        write(foo / "requirements" / "R-FOO-001.md",
              "# R-FOO-001\n\n**R-FOO-001** — The foo widget MUST frobnicate.\n"
              + ADDED_SPEC_LINE + "\n")
        write(sealy / "component.md",
              component_md("comp-sealy", "Sealy", ["sealed: true", "source_path: legacy/sealy/"]))
        write(repo_root / "gen" / "pinny" / ".overrides.json",
              '[{"file": "pinny.py", "reason": "hand-tuned"}]\n')
    else:
        write(foo / "requirements" / "R-FOO-001.md",
              "# R-FOO-001\n\n**R-FOO-001** — The foo widget MUST frobnicate.\n"
              + ADDED_SPEC_LINE + "\n")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "pr change")
    return repo_root, log_path


def parse_sections(md):
    sections = {}
    order = []
    current = None
    in_fence = False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            if current is not None:
                sections[current].append(line)
            continue
        if not in_fence:
            m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
            if m:
                current = m.group(2).strip().lower()
                if current not in sections:
                    sections[current] = []
                    order.append(current)
                continue
        if current is not None:
            sections[current].append(line)
    return order, {k: "\n".join(v) for k, v in sections.items()}


def section(md, keyword):
    order, secs = parse_sections(md)
    for heading in order:
        if keyword in heading:
            return secs[heading]
    raise AssertionError("no section heading containing " + repr(keyword) + " in:\n" + md)


def run_main(repo_root, capsys):
    capsys.readouterr()
    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo_root)]
    )
    out = capsys.readouterr().out
    return code, out


# ---------------------------------------------------------------- tests

def test_markdown_renders_real_content_for_every_section(tmp_path, capsys):
    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report("comp-foo", 0.5),
                "license_scan": license_scan_result(True),
                "secret_scan": secret_scan_result([]),
            },
        },
        "capabilities": {
            "P-FOO-CAP": {
                "hit": True,
                "capability_scenario_report": {"P-FOO-CAP": {"overall": "pass", "scenarios": []}},
            },
        },
        "secret_scan": secret_scan_result(
            [{"rule_id": "AWS Access Key", "risk_tier": "high", "file": "a/b.py", "line": 3}]
        ),
        "not_ready_reasons": ["comp-foo: license scan blocked", "secret scan flagged"],
    }
    repo_root, log_path = build_repo(tmp_path, report, with_pr_changes=True)

    code, out = run_main(repo_root, capsys)
    assert code == 0, out
    assert log_path.is_file() and "check_readiness" in log_path.read_text()

    license_sec = section(out, "license scan")
    assert "evil-gpl-lib" in license_sec or "vendored_evil.py" in license_sec, license_sec

    secret_sec = section(out, "secret scan")
    assert "a/b.py" in secret_sec, secret_sec

    residual_sec = section(out, "residual")
    assert "comp-foo" in residual_sec, residual_sec
    assert any(l.strip().startswith("-") for l in residual_sec.splitlines()), residual_sec

    cap_sec = section(out, "capability")
    assert "P-FOO-CAP" in cap_sec, cap_sec

    exemption_sec = section(out, "exemption")
    assert "**Sealed:**" in exemption_sec, exemption_sec
    assert "**Pinned Overrides:**" in exemption_sec, exemption_sec
    assert "comp-sealy" in exemption_sec, exemption_sec
    assert "comp-pinny" in exemption_sec, exemption_sec

    diff_sec = section(out, "diff")
    assert ADDED_SPEC_LINE in diff_sec, diff_sec

    assert "R-FOO-001" in out

    regen_sec = section(out, "regenerated")
    assert "comp-foo" in regen_sec, regen_sec

    prov_sec = section(out, "provenance")
    foo_lines = [l for l in prov_sec.splitlines() if "comp-foo" in l]
    assert foo_lines, prov_sec
    assert any(("true" in l.lower()) or ("hit" in l.lower()) for l in foo_lines), prov_sec


def test_markdown_renders_clean_placeholders_when_nothing_flagged(tmp_path, capsys):
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report("comp-foo", 1.0),
                "license_scan": license_scan_result(False),
                "secret_scan": secret_scan_result([]),
            },
        },
        "capabilities": {},
        "secret_scan": secret_scan_result([]),
        "not_ready_reasons": [],
    }
    repo_root, log_path = build_repo(tmp_path, report, with_pr_changes=False)

    code, out = run_main(repo_root, capsys)
    assert code == 0, out

    for keyword in ("license scan", "secret scan", "capability"):
        body = section(out, keyword)
        assert body.strip(), "section " + repr(keyword) + " has no placeholder:\n" + out
        assert "comp-foo" not in body, body
        assert "P-" not in body, body

    verif_sec = section(out, "verification")
    assert "comp-foo" in verif_sec, verif_sec