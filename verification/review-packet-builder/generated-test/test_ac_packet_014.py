import json
import os
import re
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


ADDED_SPEC_LINE = "The foo MUST also emit a zorblax frobnication receipt."


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        env=env,
    )


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component_md(cid, title, extra=""):
    return (
        "---\n"
        f"id: {cid}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        f"{extra}"
        "---\n\n"
        f"# {title}\n\nA synthetic fixture component.\n"
    )


def _verification_report(cid, mutation_score):
    return {
        "component_id": cid,
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
        "overall": "pass",
    }


def _fake_tracker_source(report, log_path):
    return (
        "import json\n\n"
        f"_REPORT = {repr(report)}\n\n"
        f"_LOG = {repr(str(log_path))}\n\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'fn': 'check_readiness', 'changed_ids': list(changed_ids) if changed_ids is not None else None}) + '\\n')\n"
        "    return _REPORT\n\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _build_repo(tmp_path, report, with_capability_spec):
    repo = tmp_path / "repo"
    repo.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _git(repo, "init")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")

    # --- base state ---
    _write(repo / "specs/components/foo/component.md", _component_md("comp-foo", "Foo"))
    _write(
        repo / "specs/components/foo/requirements/R-FOO-001.md",
        "**R-FOO-001** — The foo MUST frobnicate.\n",
    )
    _write(
        repo / "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )

    _write(
        repo / "specs/components/bar/component.md",
        _component_md("comp-bar", "Bar", "sealed: false\n"),
    )
    _write(
        repo / "specs/components/bar/requirements/R-BAR-001.md",
        "**R-BAR-001** — The bar MUST exist.\n",
    )
    _write(
        repo / "specs/components/bar/acceptance/AC-BAR-001.md",
        "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: compiled\n",
    )
    _write(repo / "legacy/bar/bar.py", "def bar():\n    return 1\n")

    _write(repo / "specs/components/baz/component.md", _component_md("comp-baz", "Baz"))
    _write(
        repo / "specs/components/baz/requirements/R-BAZ-001.md",
        "**R-BAZ-001** — The baz MUST exist.\n",
    )
    _write(
        repo / "specs/components/baz/acceptance/AC-BAZ-001.md",
        "# AC-BAZ-001\n\nCovers: R-BAZ-001\nKind: compiled\n",
    )
    _write(repo / "gen/baz/baz.py", "def baz():\n    return 2\n")

    if with_capability_spec:
        _write(
            repo / "specs/capabilities/P-FOO-CAP.md",
            "---\n"
            "id: P-FOO-CAP\n"
            "title: Foo capability\n"
            "status: draft\n"
            "owners: [alice]\n"
            "realizes: [comp-foo]\n"
            "---\n\n# Foo capability\n",
        )

    _write(
        repo / "gen/provenance-tracker/provenance_tracker.py",
        _fake_tracker_source(report, log_path),
    )

    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")

    # --- PR state ---
    _git(repo, "checkout", "-b", "feature")
    req = repo / "specs/components/foo/requirements/R-FOO-001.md"
    req.write_text(req.read_text() + ADDED_SPEC_LINE + "\n")
    _write(
        repo / "specs/components/bar/component.md",
        _component_md("comp-bar", "Bar", "sealed: true\nsource_path: legacy/bar/\n"),
    )
    _write(
        repo / "gen/baz/.overrides.json",
        json.dumps({"overrides": [{"path": "baz.py", "reason": "hand-tuned"}]}, indent=2) + "\n",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "pr change")

    # Make an origin/main ref available too, for implementations diffing against it.
    try:
        _git(repo, "remote", "add", "origin", str(repo))
        _git(repo, "fetch", "origin")
        _git(repo, "remote", "set-head", "origin", "main")
    except subprocess.CalledProcessError:
        pass

    return repo, log_path


def _run_main(argv, capsys):
    try:
        rc = review_packet_builder.main(argv)
    except SystemExit as exc:
        rc = exc.code
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _sections(md):
    """Return list of (heading_text, body) using any heading as a boundary,
    ignoring lines inside fenced code blocks."""
    result = []
    current_heading = None
    current_body = []
    in_fence = False
    for line in md.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if current_heading is not None:
                current_body.append(line)
            continue
        m = None if in_fence else _HEADING_RE.match(line)
        if m:
            if current_heading is not None:
                result.append((current_heading, "\n".join(current_body)))
            current_heading = m.group(2).strip()
            current_body = []
        elif current_heading is not None:
            current_body.append(line)
    if current_heading is not None:
        result.append((current_heading, "\n".join(current_body)))
    return result


def _norm(text):
    return text.strip().rstrip(":").strip().lower()


def _section(md, name):
    secs = _sections(md)
    for heading, body in secs:
        if _norm(heading) == name.lower():
            return body
    for heading, body in secs:
        if name.lower() in _norm(heading):
            return body
    raise AssertionError(f"no section heading {name!r} in markdown:\n{md}")


def _find_section_containing(md, keyword):
    for heading, body in _sections(md):
        if keyword.lower() in _norm(heading):
            return body
    return None


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_markdown_renders_real_detail_for_every_section(tmp_path, capsys):
    license_result = {
        "blocked": True,
        "findings": [
            {
                "file": "gen/foo/vendor/gplthing/gpl_lib.py",
                "package": "gplthing",
                "license": "GPL-3.0-only",
            }
        ],
    }
    secret_result = {
        "flagged": True,
        "findings": [
            {
                "file": "gen/foo/foo_config.py",
                "line": 12,
                "kind": "aws-access-key",
            }
        ],
    }
    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report("comp-foo", 0.92),
                "license_scan": license_result,
                "secret_scan": secret_result,
            }
        },
        "capabilities": {
            "P-FOO-CAP": {
                "hit": True,
                "capability_scenario_report": {
                    "P-FOO-CAP": {"overall": "pass", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [
            "comp-foo: license scan blocked",
            "comp-foo: secret scan flagged",
        ],
    }
    repo, log_path = _build_repo(tmp_path, report, with_capability_spec=True)

    rc, out, err = _run_main(
        ["review-packet", "build", "--changed=R-FOO-001", f"--repo-root={repo}"],
        capsys,
    )
    assert rc == 0, f"exit {rc!r}; stdout={out!r}; stderr={err!r}"
    assert log_path.exists(), "the fake provenance-tracker's check_readiness was never invoked"

    md = out

    # License Scan: the flag's own detail content, not merely a status word.
    lic = _section(md, "License Scan")
    assert "gplthing" in lic or "gpl_lib.py" in lic, (
        f"License Scan section lacks the flagged package/file detail:\n{lic}"
    )

    # Secret Scan: the flag's own detail content, not merely a status word.
    sec = _section(md, "Secret Scan")
    assert "foo_config.py" in sec or "aws-access-key" in sec, (
        f"Secret Scan section lacks the flagged file/kind detail:\n{sec}"
    )

    # Residual Risk: the residual-risk message for comp-foo.
    rr = _section(md, "Residual Risk")
    assert "comp-foo" in rr, f"Residual Risk section lacks component id:\n{rr}"
    assert "0.92" in rr or "mutation" in rr.lower(), (
        f"Residual Risk section lacks the mutation-score message:\n{rr}"
    )

    # Capability Scenarios: the capability id.
    cap = _section(md, "Capability Scenarios")
    assert "P-FOO-CAP" in cap, f"Capability Scenarios section lacks P-FOO-CAP:\n{cap}"

    # Exemption Changes: sealed and pinned-override component ids under their labels.
    ex = _section(md, "Exemption Changes")
    assert "**Sealed:**" in ex, f"Exemption Changes lacks **Sealed:** label:\n{ex}"
    assert "**Pinned Overrides:**" in ex, (
        f"Exemption Changes lacks **Pinned Overrides:** label:\n{ex}"
    )
    s_idx = ex.index("**Sealed:**")
    p_idx = ex.index("**Pinned Overrides:**")
    if s_idx < p_idx:
        sealed_part = ex[s_idx:p_idx]
        pinned_part = ex[p_idx:]
    else:
        pinned_part = ex[p_idx:s_idx]
        sealed_part = ex[s_idx:]
    assert "comp-bar" in sealed_part, f"sealed component id missing:\n{ex}"
    assert "comp-baz" in pinned_part, f"pinned-override component id missing:\n{ex}"

    # Spec diff text: the line this PR added under specs/.
    assert ADDED_SPEC_LINE in md, f"spec diff text missing the added line:\n{md}"

    # Changed requirement id.
    assert "R-FOO-001" in md

    # Regenerated component id, with real verification content.
    assert "comp-foo" in md
    vr = _section(md, "Verification Results")
    assert "comp-foo" in vr, f"Verification Results lacks comp-foo:\n{vr}"

    regen = _find_section_containing(md, "regenerated")
    if regen is not None:
        assert "comp-foo" in regen, f"Regenerated section lacks comp-foo:\n{regen}"

    # Provenance hit status for the regenerated component.
    prov = _find_section_containing(md, "provenance")
    if prov is not None:
        assert "comp-foo" in prov, f"provenance hit status section lacks comp-foo:\n{prov}"
        assert "true" in prov.lower() or "hit" in prov.lower(), (
            f"provenance hit status section lacks the hit status:\n{prov}"
        )
    else:
        lines = [l for l in md.splitlines() if "comp-foo" in l]
        assert any(
            ("true" in l.lower() or "hit" in l.lower()) for l in lines
        ), f"no line renders comp-foo's provenance hit status:\n{md}"


def test_markdown_renders_clean_placeholders_when_nothing_flagged(tmp_path, capsys):
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report("comp-foo", 1.0),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
    repo, log_path = _build_repo(tmp_path, report, with_capability_spec=False)

    rc, out, err = _run_main(
        ["review-packet", "build", "--changed=R-FOO-001", f"--repo-root={repo}"],
        capsys,
    )
    assert rc == 0, f"exit {rc!r}; stdout={out!r}; stderr={err!r}"
    assert log_path.exists(), "the fake provenance-tracker's check_readiness was never invoked"

    md = out

    for name in ("License Scan", "Secret Scan", "Capability Scenarios"):
        body = _section(md, name)
        assert body.strip(), (
            f"{name} section renders no clean/empty placeholder of its own:\n{md}"
        )
        assert "P-FOO-CAP" not in body

    vr = _section(md, "Verification Results")
    assert "comp-foo" in vr, (
        f"Verification Results lacks real content for comp-foo:\n{vr}"
    )