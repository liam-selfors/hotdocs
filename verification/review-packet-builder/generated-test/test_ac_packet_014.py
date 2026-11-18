# hotdocs-criterion: sha256:15b32d995dc720ab6fa7ff6104ad7efb379fd5d873a4faf098be550ad5d652fd
import json
import re
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


LICENSE_PACKAGE = "gplthing-pkg-9931"
LICENSE_FILE = "vendor/gplthing_9931/core.py"
SECRET_FILE = "config/leaky_secrets_7742.py"
SPEC_DIFF_LINE = "The component MUST frobnicate the quux-5521 widget on every call."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=Test User",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, extra_lines):
    text = "---\n"
    text += "id: " + comp_id + "\n"
    text += "title: " + title + "\n"
    text += "status: draft\n"
    text += "owners: [alice]\n"
    for line in extra_lines:
        text += line + "\n"
    text += "---\n\n"
    text += "# " + title + "\n\n"
    text += "A fixture component.\n"
    return text


def _add_unit_files(repo_root, slug, upper):
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        repo_root / "specs" / "components" / slug / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The component MUST do its job.\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: generated-test\n\n"
        "Given a thing\nWhen it runs\nThen it works\n",
    )


def _verification_report(mutation_score):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "generated-test",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": mutation_score,
        "mutation_error": None,
        "overall": "pass",
    }


def _flagged_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(0.92),
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
                            "line": 3,
                            "kind": "aws-access-key",
                        }
                    ],
                },
            }
        },
        "capabilities": {
            "P-FOO": {
                "hit": True,
                "capability_scenario_report": {
                    "P-FOO": {"overall": "pass", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [
            "comp-foo: license scan blocked",
            "comp-foo: secret scan flagged",
        ],
    }


def _clean_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(1.0),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _fake_tracker_source(report, log_path):
    src = ""
    src += "import copy\n"
    src += "\n"
    src += "LOG_PATH = " + repr(str(log_path)) + "\n"
    src += "REPORT = " + repr(report) + "\n"
    src += "\n"
    src += "\n"
    src += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    src += "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    src += "        fh.write('check_readiness ' + repr(list(changed_ids) if changed_ids is not None else None) + '\\n')\n"
    src += "    return copy.deepcopy(REPORT)\n"
    src += "\n"
    src += "\n"
    src += "def last_requirement_failures(component_id, repo_root):\n"
    src += "    return []\n"
    return src


def _build_repo(repo_root, report, log_path):
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init")
    _git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")

    # --- base commit ---
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a fixture term.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        _component_md("comp-foo", "Foo", ["sealed: false", "realizes: [P-FOO]"]),
    )
    _add_unit_files(repo_root, "foo", "FOO")
    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        _component_md("comp-bar", "Bar", ["sealed: false"]),
    )
    _add_unit_files(repo_root, "bar", "BAR")
    _write(
        repo_root / "specs" / "components" / "baz" / "component.md",
        _component_md("comp-baz", "Baz", ["sealed: false"]),
    )
    _add_unit_files(repo_root, "baz", "BAZ")
    _write(repo_root / "gen" / "baz" / "baz.py", "def baz():\n    return 1\n")
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _fake_tracker_source(report, log_path),
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "base")

    # --- PR commit on a feature branch ---
    _git(repo_root, "checkout", "-b", "feature")
    req_path = repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
    req_path.write_text(
        req_path.read_text(encoding="utf-8") + "\n" + SPEC_DIFF_LINE + "\n",
        encoding="utf-8",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        _component_md("comp-bar", "Bar", ["sealed: true", "source_path: legacy/bar/"]),
    )
    _write(
        repo_root / "gen" / "baz" / ".overrides.json",
        json.dumps({"pinned": [{"path": "baz.py", "reason": "hand-tuned"}]}, indent=2) + "\n",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "pr change")


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _section(md, names):
    """Return the body under the first heading whose title contains any of
    `names` (case-insensitive), up to the next heading of the same or a
    higher level. Fenced code blocks are skipped when looking for headings."""
    lines = md.splitlines()
    for name in names:
        in_fence = False
        for i, line in enumerate(lines):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = _HEADING_RE.match(line)
            if m and name.lower() in m.group(2).lower():
                level = len(m.group(1))
                body = []
                inner_fence = False
                for line2 in lines[i + 1:]:
                    if line2.lstrip().startswith("```"):
                        inner_fence = not inner_fence
                        body.append(line2)
                        continue
                    if not inner_fence:
                        m2 = re.match(r"^(#{1,6})\s", line2)
                        if m2 and len(m2.group(1)) <= level:
                            break
                    body.append(line2)
                return "\n".join(body)
    return None


def _label_segment(section_text, label, other_label):
    start = section_text.find(label)
    assert start != -1, "missing label " + repr(label) + " in:\n" + section_text
    rest = section_text[start + len(label):]
    end = rest.find(other_label)
    if end != -1:
        rest = rest[:end]
    return rest


def _run_main(repo_root, capsys):
    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo_root)]
    )
    out = capsys.readouterr().out
    return rc, out


def test_markdown_renders_real_detail_for_every_section(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "tracker_calls.log"
    _build_repo(repo_root, _flagged_report(), log_path)

    rc, md = _run_main(repo_root, capsys)
    assert rc == 0, md
    assert log_path.is_file() and "check_readiness" in log_path.read_text(encoding="utf-8"), (
        "the fake provenance-tracker was never called"
    )

    # License scan: real flagged detail, not merely a status word.
    license_sec = _section(md, ["License Scan"])
    assert license_sec is not None, "no License Scan heading in:\n" + md
    assert LICENSE_PACKAGE in license_sec, license_sec
    assert LICENSE_FILE in license_sec, license_sec

    # Secret scan: real flagged detail, not merely a status word.
    secret_sec = _section(md, ["Secret Scan"])
    assert secret_sec is not None, "no Secret Scan heading in:\n" + md
    assert SECRET_FILE in secret_sec, secret_sec

    # Residual risk: the real message(s) the packet carries.
    packet = review_packet_builder.build_review_packet(["R-FOO-001"], repo_root)
    residual = field(packet, "residual_risk")
    assert len(residual) >= 1, residual
    residual_sec = _section(md, ["Residual Risk"])
    assert residual_sec is not None, "no Residual Risk heading in:\n" + md
    for entry in residual:
        message = field(entry, "message")
        assert isinstance(message, str) and message.strip()
        assert message in residual_sec, (message, residual_sec)

    # Capability scenarios: the capability id under its own heading.
    cap_sec = _section(md, ["Capability Scenarios"])
    assert cap_sec is not None, "no Capability Scenarios heading in:\n" + md
    assert "P-FOO" in cap_sec, cap_sec

    # Exemption changes: sealed and pinned-override component ids.
    exempt_sec = _section(md, ["Exemption Changes"])
    assert exempt_sec is not None, "no Exemption Changes heading in:\n" + md
    sealed_seg = _label_segment(exempt_sec, "**Sealed:**", "**Pinned Overrides:**")
    pinned_seg = _label_segment(exempt_sec, "**Pinned Overrides:**", "**Sealed:**")
    assert "comp-bar" in sealed_seg, exempt_sec
    assert "comp-baz" in pinned_seg, exempt_sec

    # Spec diff text: the line this PR added under specs/.
    assert SPEC_DIFF_LINE in md, md

    # Changed requirement and regenerated component.
    assert "R-FOO-001" in md, md
    assert "comp-foo" in md, md

    # Verification results: real content for the regenerated component.
    vr_sec = _section(md, ["Verification Results"])
    assert vr_sec is not None, "no Verification Results heading in:\n" + md
    assert "comp-foo" in vr_sec, vr_sec
    assert "pass" in vr_sec, vr_sec

    # Provenance hit status for the regenerated component.
    prov_sec = _section(md, ["Provenance Hit", "Provenance"])
    assert prov_sec is not None, "no provenance hit status heading in:\n" + md
    foo_lines = [ln for ln in prov_sec.splitlines() if "comp-foo" in ln]
    assert foo_lines, prov_sec
    joined = " ".join(foo_lines).lower()
    assert ("true" in joined) or ("hit" in joined) or ("yes" in joined), prov_sec


def test_markdown_renders_clean_placeholders_when_nothing_flagged(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "tracker_calls.log"
    _build_repo(repo_root, _clean_report(), log_path)

    rc, md = _run_main(repo_root, capsys)
    assert rc == 0, md
    assert log_path.is_file() and "check_readiness" in log_path.read_text(encoding="utf-8"), (
        "the fake provenance-tracker was never called"
    )

    for name in ["License Scan", "Secret Scan", "Capability Scenarios"]:
        sec = _section(md, [name])
        assert sec is not None, "no " + name + " heading in:\n" + md
        assert sec.strip(), name + " section has no placeholder at all:\n" + md
        assert "comp-foo" not in sec, name + " should be empty but lists comp-foo:\n" + sec
        assert "P-FOO" not in sec, sec

    vr_sec = _section(md, ["Verification Results"])
    assert vr_sec is not None, "no Verification Results heading in:\n" + md
    foo_lines = [ln for ln in vr_sec.splitlines() if "comp-foo" in ln]
    assert foo_lines, vr_sec
    assert "pass" in vr_sec, vr_sec