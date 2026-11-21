# hotdocs-criterion: sha256:9e41df482a2671228f0cc2b85209676cf8900371809ad76a593ed0d861a4c629
import json
import re
import subprocess
from pathlib import Path

import review_packet_builder


ADDED_SPEC_LINE = "This PR adds a brand-new clarifying sentence for R-FOO-001 zeta-marker."
LICENSE_PACKAGE = "gpl-widget-lib"
LICENSE_FILE = "vendor/gpl_widget_core.c"
SECRET_FILE = "config/leaked_creds_module.py"
SECRET_KIND = "aws-access-key-id"
CAP_ID = "P-FOO-CAP"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def verification_report(component_id, mutation_score):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": mutation_score,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "a" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }


def flagged_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report("comp-foo", 0.92),
                "license_scan": {
                    "blocked": True,
                    "findings": [
                        {
                            "file": LICENSE_FILE,
                            "package": LICENSE_PACKAGE,
                            "license": "GPL-3.0-only",
                        }
                    ],
                },
                "secret_scan": {
                    "flagged": True,
                    "findings": [
                        {
                            "file": SECRET_FILE,
                            "line": 7,
                            "kind": SECRET_KIND,
                        }
                    ],
                },
            }
        },
        "capabilities": {
            CAP_ID: {
                "hit": True,
                "capability_scenario_report": {
                    CAP_ID: {"overall": "pass", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [
            "comp-foo: license scan blocked",
            "comp-foo: secret scan flagged",
        ],
    }


def clean_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report("comp-foo", 1.0),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def fake_tracker_source(report, log_path):
    return (
        "import copy\n"
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(json.dumps({'call': 'check_readiness', 'changed_ids': list(changed_ids) if changed_ids is not None else None}) + '\\n')\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(json.dumps({'call': 'last_requirement_failures', 'component_id': component_id}) + '\\n')\n"
        "    return []\n"
    )


def foo_component_md():
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [" + CAP_ID + "]\n"
        "---\n"
        "\n"
        "Foo component.\n"
    )


def bar_component_md(sealed):
    text = (
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
    )
    if sealed:
        text += "sealed: true\nsource_path: legacy/bar/\n"
    else:
        text += "sealed: false\n"
    text += "---\n\nBar component.\n"
    return text


def build_repo(tmp_path, report, with_exemptions):
    repo = tmp_path / "repo"
    repo.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "checkout", "-q", "-b", "main")

    write(repo / "specs" / "components" / "foo" / "component.md", foo_component_md())
    write(
        repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** - Foo MUST do the foo thing.\n",
    )
    write(
        repo / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )
    write(
        repo / "specs" / "capabilities" / (CAP_ID + ".md"),
        "---\n"
        "id: " + CAP_ID + "\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [comp-foo]\n"
        "---\n\nFoo capability.\n",
    )
    if with_exemptions:
        write(repo / "specs" / "components" / "bar" / "component.md", bar_component_md(False))
    write(
        repo / "gen" / "provenance-tracker" / "provenance_tracker.py",
        fake_tracker_source(report, log_path),
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")

    git(repo, "checkout", "-q", "-b", "feature")
    req = repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
    req.write_text(req.read_text() + ADDED_SPEC_LINE + "\n")
    if with_exemptions:
        write(repo / "specs" / "components" / "bar" / "component.md", bar_component_md(True))
        write(
            repo / "gen" / "baz" / ".overrides.json",
            json.dumps({"files": {"baz.py": "hand-maintained"}}, indent=2, sort_keys=True) + "\n",
        )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "pr change")
    return repo, log_path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def parse_sections(md):
    sections = []
    current = None
    in_fence = False
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if current is not None:
                current[1].append(line)
            continue
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            current = (m.group(2), [])
            sections.append(current)
        elif current is not None:
            current[1].append(line)
    return [(title, "\n".join(body)) for title, body in sections]


def section_body(md, pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    bodies = [body for title, body in parse_sections(md) if rx.search(title)]
    assert bodies, "no section heading matching " + repr(pattern) + " in:\n" + md
    return "\n".join(bodies)


def run_main(repo, capsys):
    capsys.readouterr()
    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo)]
    )
    out = capsys.readouterr().out
    return code, out


def test_markdown_renders_real_detail_for_every_section(tmp_path, capsys):
    repo, log_path = build_repo(tmp_path, flagged_report(), with_exemptions=True)

    code, md = run_main(repo, capsys)
    assert code == 0, md
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text()

    # License flag detail, not merely a status word.
    license_body = section_body(md, r"license\s*scan")
    assert LICENSE_PACKAGE in license_body or LICENSE_FILE in license_body, license_body

    # Secret flag detail, not merely a status word.
    secret_body = section_body(md, r"secret\s*scan")
    assert SECRET_FILE in secret_body or SECRET_KIND in secret_body, secret_body

    # Residual risk: the real message(s) the packet itself carries.
    packet = review_packet_builder.build_review_packet(["R-FOO-001"], repo)
    residual = field(packet, "residual_risk")
    assert len(residual) >= 1
    residual_body = section_body(md, r"residual\s*risk")
    for entry in residual:
        message = field(entry, "message")
        assert isinstance(message, str) and message.strip()
        assert message in residual_body, (message, residual_body)

    # Capability scenario id.
    cap_body = section_body(md, r"capabilit")
    assert CAP_ID in cap_body, cap_body

    # Exemption changes: sealed and pinned override component ids under labels.
    exempt_body = section_body(md, r"exemption")
    sealed_label = "**Sealed:**"
    pinned_label = "**Pinned Overrides:**"
    assert sealed_label in exempt_body, exempt_body
    assert pinned_label in exempt_body, exempt_body
    s = exempt_body.index(sealed_label)
    p = exempt_body.index(pinned_label)
    if s < p:
        sealed_seg = exempt_body[s:p]
        pinned_seg = exempt_body[p:]
    else:
        pinned_seg = exempt_body[p:s]
        sealed_seg = exempt_body[s:]
    assert "comp-bar" in sealed_seg, exempt_body
    assert "comp-baz" in pinned_seg, exempt_body

    # Spec diff: the line this PR added under specs/, and nothing outside specs/.
    diff_body = section_body(md, r"diff")
    assert ADDED_SPEC_LINE in diff_body, diff_body
    assert ".overrides.json" not in diff_body, diff_body

    # Changed requirement id.
    req_body = section_body(md, r"requirement")
    assert "R-FOO-001" in req_body, req_body

    # Regenerated component id.
    regen_body = section_body(md, r"regenerat")
    assert "comp-foo" in regen_body, regen_body

    # Provenance hit status for the regenerated component (a hit here).
    prov_body = section_body(md, r"provenance")
    lines = [ln for ln in prov_body.splitlines() if "comp-foo" in ln]
    assert lines, prov_body
    line = " ".join(lines).lower()
    assert any(tok in line for tok in ("true", "hit", "yes", "\u2713", "\u2705", "reused", "cached")), line
    assert "false" not in line and "miss" not in line, line

    # Verification results render real content for comp-foo.
    ver_body = section_body(md, r"verification\s*results")
    assert "comp-foo" in ver_body, ver_body


def test_markdown_renders_clean_placeholders_when_nothing_flagged(tmp_path, capsys):
    repo, log_path = build_repo(tmp_path, clean_report(), with_exemptions=False)

    code, md = run_main(repo, capsys)
    assert code == 0, md
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text()

    for pattern in (r"license\s*scan", r"secret\s*scan", r"capabilit"):
        body = section_body(md, pattern)
        assert body.strip(), "section " + repr(pattern) + " has no placeholder:\n" + md

    cap_body = section_body(md, r"capabilit")
    assert CAP_ID not in cap_body, cap_body

    ver_body = section_body(md, r"verification\s*results")
    assert "comp-foo" in ver_body, ver_body