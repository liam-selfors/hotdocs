import os
import re
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git_env():
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Test Author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


def _git(root, *args):
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=str(root),
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    )
    return result.stdout


def _commit_all(root, message):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--allow-empty", "-m", message)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _verification_report(component_id, slug_upper):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": f"AC-{slug_upper}-001",
                "covers": f"R-{slug_upper}-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {f"R-{slug_upper}-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "overall": "pass",
    }


def _write_provenance_tracker_standin(root, component_ids):
    components = {}
    for cid in component_ids:
        slug_upper = cid[len("comp-"):].upper().replace("-", "_")
        components[cid] = {
            "hit": True,
            "verification_report": _verification_report(cid, slug_upper),
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
    source = (
        "REPORT = " + repr(report) + "\n\n\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    import copy\n"
        "    result = copy.deepcopy(REPORT)\n"
        "    result['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return result\n\n\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


def _component_md(slug, sealed_line):
    lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {slug.capitalize()} component",
        "status: draft",
        "owners: [alice]",
    ]
    if sealed_line is not None:
        lines.append(sealed_line)
    lines.append(f"source_path: legacy/{slug}/")
    lines.append("---")
    lines.append("")
    lines.append(f"# comp-{slug}")
    lines.append("")
    lines.append(f"Fixture component {slug}.")
    lines.append("")
    return "\n".join(lines)


def _write_component(root, slug, sealed_line, body_suffix=""):
    upper = slug.upper().replace("-", "_")
    base = root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, sealed_line) + body_suffix)
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"**R-{upper}-001** — The {slug} component MUST do its one thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )


def _init_repo(root, standin_ids):
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    _write(root / "README.md", "fixture repo\n")
    _write_provenance_tracker_standin(root, standin_ids)


def _build_sealed_only_repo(root):
    _init_repo(root, ["comp-foo"])
    _commit_all(root, "base")
    _git(root, "checkout", "-q", "-b", "feature")
    # First commit of the component: no sealed line at all.
    _write_component(root, "foo", None)
    _commit_all(root, "add comp-foo (unsealed)")
    # Second real commit: change it to sealed: true.
    _write_component(root, "foo", "sealed: true")
    _commit_all(root, "seal comp-foo")
    return root


def _build_no_transition_repo(root):
    _init_repo(root, ["comp-alpha", "comp-beta"])
    # gen/comp-old/.overrides.json present at the PR diff-base.
    _write(
        root / "gen" / "comp-old" / ".overrides.json",
        '{"files": ["comp_old.py"]}\n',
    )
    _commit_all(root, "base with comp-old override")
    _git(root, "checkout", "-q", "-b", "feature")
    # comp-alpha: sealed from birth, then edited (still sealed).
    _write_component(root, "alpha", "sealed: true")
    # comp-beta: first committed with no sealed line.
    _write_component(root, "beta", None)
    _commit_all(root, "add alpha (sealed) and beta (no sealed line)")
    _write_component(root, "alpha", "sealed: true", body_suffix="\nAn edit.\n")
    _commit_all(root, "edit alpha, still sealed")
    _write_component(root, "beta", "sealed: false")
    _commit_all(root, "beta: sealed false")
    # Delete the override in this PR.
    (root / "gen" / "comp-old" / ".overrides.json").unlink()
    _commit_all(root, "delete comp-old override")
    return root


def _run_main(argv):
    try:
        rc = review_packet_builder.main(argv)
    except SystemExit as exc:
        rc = exc.code
    return rc


_HEADING = re.compile(r"^(#+)\s")


def _exemption_section(md):
    lines = md.splitlines()
    start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if _HEADING.match(s) and "exemption changes" in s.lower():
            start = i
            break
    if start is None:
        for i, line in enumerate(lines):
            if "exemption changes" in line.lower():
                start = i
                break
    assert start is not None, f"No 'Exemption Changes' section in markdown:\n{md}"
    m = _HEADING.match(lines[start].strip())
    level = len(m.group(1)) if m else None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j].strip()
        hm = _HEADING.match(s)
        if not hm:
            continue
        low = s.lower()
        if level is not None:
            if len(hm.group(1)) <= level:
                end = j
                break
        else:
            if "sealed" not in low and "pinned" not in low:
                end = j
                break
    return lines[start + 1:end]


def _split_sealed_pinned(section_lines):
    sealed_idx = None
    pinned_idx = None
    for i, line in enumerate(section_lines):
        low = line.lower()
        if sealed_idx is None and "sealed" in low and "pinned" not in low:
            sealed_idx = i
        if pinned_idx is None and "pinned" in low and "sealed" not in low:
            pinned_idx = i
    joined = "\n".join(section_lines)
    assert sealed_idx is not None, f"No Sealed list in Exemption Changes:\n{joined}"
    assert pinned_idx is not None, (
        f"No Pinned Overrides list in Exemption Changes:\n{joined}"
    )
    if sealed_idx < pinned_idx:
        sealed_part = section_lines[sealed_idx:pinned_idx]
        pinned_part = section_lines[pinned_idx:]
    else:
        pinned_part = section_lines[pinned_idx:sealed_idx]
        sealed_part = section_lines[sealed_idx:]
    return "\n".join(sealed_part), "\n".join(pinned_part)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_sealed_transition_detected_in_library(tmp_path):
    root = _build_sealed_only_repo(tmp_path / "repo")

    packet = review_packet_builder.build_review_packet(["comp-foo"], root)

    exemption = field(packet, "exemption_changes")
    sealed = list(field(exemption, "sealed"))
    pinned = list(field(exemption, "pinned_overrides"))
    assert "comp-foo" in sealed
    assert "comp-foo" not in pinned
    assert pinned == []


def test_sealed_only_pr_markdown_lists_sealed_not_pinned(tmp_path, capsys):
    root = _build_sealed_only_repo(tmp_path / "repo")

    rc = _run_main(
        ["review-packet", "build", "--changed", "comp-foo", "--repo-root", str(root)]
    )
    out = capsys.readouterr().out
    assert rc in (0, None), f"exit code {rc}, output:\n{out}"

    section = _exemption_section(out)
    sealed_part, pinned_part = _split_sealed_pinned(section)

    assert "comp-foo" in sealed_part, (
        f"Sealed list missing comp-foo:\n{sealed_part}"
    )
    assert "comp-foo" not in pinned_part, (
        f"Pinned Overrides wrongly lists comp-foo:\n{pinned_part}"
    )
    assert re.search(r"comp-[A-Za-z0-9_-]+", pinned_part) is None, (
        f"Pinned Overrides should render as empty:\n{pinned_part}"
    )


def test_no_transition_and_deleted_override_not_reported(tmp_path):
    root = _build_no_transition_repo(tmp_path / "repo")

    packet = review_packet_builder.build_review_packet(
        ["comp-alpha", "comp-beta"], root
    )

    exemption = field(packet, "exemption_changes")
    sealed = list(field(exemption, "sealed"))
    pinned = list(field(exemption, "pinned_overrides"))
    assert "comp-alpha" not in sealed
    assert "comp-beta" not in sealed
    assert "comp-old" not in pinned