# hotdocs-criterion: sha256:89086513bc88ef99e04b14ac36a1b306fb728e39b9aca44a2dc4a6e59ae46f9b
import os
import re
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GIT_ENV = dict(os.environ)
GIT_ENV.update({
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
})


def git(repo, *args):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo), env=GIT_ENV, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ).stdout.strip()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


SPEC_MARKER = "zebra-quokka-marker-7731"
LICENSE_PKG = "evilpkg-gplthing"


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


def clean_secret_scan():
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


def build_report(flagged):
    if flagged:
        license_scan = {
            "gate_version": "license_scanner@1.0.0",
            "blocked": True,
            "findings": [
                {"package": LICENSE_PKG, "license": "GPL-3.0-only",
                 "file": "gen/foo/vendored_gplthing.py"},
            ],
        }
        mutation_score = 0.92
        top_secret = {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": True,
            "matches": [
                {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "a/b.py", "line": 3},
            ],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }
        capabilities = {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ZERO-EDIT": {"overall": "pass", "scenarios": []},
                },
            },
        }
        reasons = ["comp-foo: license scan blocked", "repository secret scan flagged"]
    else:
        license_scan = {"gate_version": "license_scanner@1.0.0", "blocked": False, "findings": []}
        mutation_score = 1.0
        top_secret = clean_secret_scan()
        capabilities = {}
        reasons = []
    return {
        "scope": "blast-radius",
        "ready": not flagged,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report("comp-foo", mutation_score),
                "license_scan": license_scan,
                "secret_scan": clean_secret_scan(),
            },
        },
        "capabilities": capabilities,
        "secret_scan": top_secret,
        "not_ready_reasons": reasons,
    }


def component_md(cid, extra):
    return ("---\nid: " + cid + "\ntitle: " + cid + "\nstatus: draft\nowners: [team]\n"
            + extra + "---\n\n# " + cid + "\n\nSome purpose.\n")


def make_repo(tmp_path, report, with_history):
    repo = tmp_path / "repo"
    repo.mkdir()
    log_path = tmp_path / "fake_calls.log"
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")

    write(repo / "specs" / "components" / "foo" / "component.md",
          component_md("comp-foo", "realizes: [P-ZERO-EDIT]\n"))
    write(repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
          "**R-FOO-001** — Foo MUST do the thing.\n")
    write(repo / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
          "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n")
    write(repo / "specs" / "components" / "sealedthing" / "component.md",
          component_md("comp-sealedthing", ""))
    write(repo / "specs" / "components" / "sealedthing" / "requirements" / "R-SEALED-001.md",
          "**R-SEALED-001** — Sealedthing MUST work.\n")
    write(repo / "specs" / "components" / "sealedthing" / "acceptance" / "AC-SEALED-001.md",
          "# AC-SEALED-001\n\nCovers: R-SEALED-001\nKind: compiled\n")
    write(repo / "specs" / "components" / "pinnedthing" / "component.md",
          component_md("comp-pinnedthing", "sealed: true\nsource_path: legacy/pinnedthing/\n"))
    write(repo / "specs" / "components" / "pinnedthing" / "requirements" / "R-PIN-001.md",
          "**R-PIN-001** — Pinnedthing MUST work.\n")
    write(repo / "specs" / "components" / "pinnedthing" / "acceptance" / "AC-PIN-001.md",
          "# AC-PIN-001\n\nCovers: R-PIN-001\nKind: compiled\n")

    fake_src = (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "_REPORT = " + repr(report) + "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write('check_readiness ' + json.dumps(list(changed_ids) if changed_ids is not None else None) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    write(repo / "gen" / "provenance-tracker" / "provenance_tracker.py", fake_src)

    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    git(repo, "checkout", "-q", "-b", "feature")

    if with_history:
        req = repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
        req.write_text(req.read_text() + "\nAdded by this PR: " + SPEC_MARKER + ".\n")
        write(repo / "specs" / "components" / "sealedthing" / "component.md",
              component_md("comp-sealedthing", "sealed: true\nsource_path: legacy/sealedthing/\n"))
        write(repo / "gen" / "pinnedthing" / ".overrides.json",
              '{"overrides": [{"path": "x.py", "reason": "hand fix"}]}\n')
    else:
        req = repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
        req.write_text(req.read_text() + "\nClarified wording.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feature change")
    return repo, log_path


def parse_sections(md):
    out = []
    cur = None
    in_fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if cur is not None:
                cur[1].append(line)
            continue
        if not in_fence and re.match(r"^#{1,6}\s", line):
            cur = [line.lstrip("#").strip(), []]
            out.append(cur)
            continue
        if cur is not None:
            cur[1].append(line)
    return [(h, "\n".join(b)) for h, b in out]


def section(md, *keywords):
    for heading, body in parse_sections(md):
        low = heading.lower()
        if any(k in low for k in keywords):
            return body
    raise AssertionError("no section heading matching " + repr(keywords) + " in:\n" + md)


def sections_matching(md, *keywords):
    return "\n".join(body for heading, body in parse_sections(md)
                     if any(k in heading.lower() for k in keywords))


def run_main(repo, capsys):
    capsys.readouterr()
    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo)])
    out = capsys.readouterr().out
    return code, out


def test_markdown_renders_real_detail_content(tmp_path, capsys):
    repo, log_path = make_repo(tmp_path, build_report(True), with_history=True)
    code, md = run_main(repo, capsys)
    assert code == 0, md
    assert log_path.is_file() and "check_readiness" in log_path.read_text()

    lic = section(md, "license")
    assert LICENSE_PKG in lic, lic

    sec = section(md, "secret")
    assert "a/b.py" in sec, sec

    rr = section(md, "residual")
    assert "comp-foo" in rr, rr
    assert "0.92" in rr or "mutation" in rr.lower(), rr

    cap = section(md, "capabilit")
    assert "P-ZERO-EDIT" in cap, cap

    ex = section(md, "exemption")
    assert "**Sealed:**" in ex, ex
    assert "**Pinned Overrides:**" in ex, ex
    assert "comp-sealedthing" in ex, ex
    assert "comp-pinnedthing" in ex, ex

    diff = section(md, "diff")
    assert SPEC_MARKER in diff, diff

    reqs = section(md, "requirement")
    assert "R-FOO-001" in reqs, reqs

    regen = sections_matching(md, "regenerat")
    assert "comp-foo" in regen, md

    prov = sections_matching(md, "provenance", "hit")
    assert "comp-foo" in prov, md
    low = prov.lower()
    assert any(w in low for w in ("true", "hit", "yes", "reused", "cached")), prov

    ver = section(md, "verification")
    assert "comp-foo" in ver, ver


def test_markdown_renders_empty_placeholders(tmp_path, capsys):
    repo, log_path = make_repo(tmp_path, build_report(False), with_history=False)
    code, md = run_main(repo, capsys)
    assert code == 0, md
    assert log_path.is_file() and "check_readiness" in log_path.read_text()

    lic = section(md, "license")
    assert lic.strip(), "License Scan section has no placeholder:\n" + md
    assert "comp-foo" not in lic, lic

    sec = section(md, "secret")
    assert sec.strip(), "Secret Scan section has no placeholder:\n" + md
    assert "a/b.py" not in sec, sec

    cap = section(md, "capabilit")
    assert cap.strip(), "Capability Scenarios section has no placeholder:\n" + md
    assert "P-ZERO-EDIT" not in cap, cap

    ver = section(md, "verification")
    assert "comp-foo" in ver, ver
    assert "pass" in ver.lower() or "overall" in ver.lower(), ver