# hotdocs-criterion: sha256:1d9624591c03844f5de474325759b7ffc8e6ab0a321171c8e4dc54bf94244a1c
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _report(include_az=False):
    report = {}
    if include_az:
        report["z"] = 1
    report.update({
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "0" * 64,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "overall": "pass",
    })
    if include_az:
        report["a"] = 2
    return report


def _verify_report(include_az=False):
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _report(include_az),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(repo, *args):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "-c", "commit.gpgsign=false"] + list(args),
                   cwd=str(repo), check=True, capture_output=True, env=env)


def _make_repo(root, mode="ok", include_az=False):
    root.mkdir(parents=True, exist_ok=True)
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md",
           "---\n"
           "id: comp-foo\n"
           "title: Foo\n"
           "status: draft\n"
           "owners: [pipeline-team]\n"
           "depends_on: []\n"
           "sealed: true\n"
           "source_path: legacy/foo/\n"
           "---\n\n# Foo\n\nA fixture component.\n")
    _write(comp / "requirements" / "R-FOO-001.md",
           "**R-FOO-001** — foo MUST do the thing.\n")
    _write(comp / "acceptance" / "AC-FOO-001.md",
           "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\nfoo does the thing.\n")
    _write(root / "legacy" / "foo" / "foo.py", "def foo():\n    return 1\n")

    log = root.parent / (root.name + "_calls.log")
    src = "import copy\n\n"
    src += "LOG = " + repr(str(log)) + "\n"
    src += "REPORT = " + repr(_verify_report(include_az)) + "\n\n"
    src += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    src += "    with open(LOG, 'a') as f:\n"
    src += "        f.write('check_readiness\\n')\n"
    if mode == "raise":
        src += "    raise ValueError(" + repr("P-FOO-CAP: capability needs a fresh run; pass --model") + ")\n"
    else:
        src += "    return copy.deepcopy(REPORT)\n"
    src += "\n\ndef last_requirement_failures(component_id, repo_root):\n"
    src += "    return []\n"
    _write(root / "gen" / "provenance-tracker" / "provenance_tracker.py", src)

    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial fixture")
    return root, log


def _run(argv, capsys):
    capsys.readouterr()
    code = review_packet_builder.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_json_build_has_real_content(tmp_path, capsys):
    repo, log = _make_repo(tmp_path / "repo")
    code, out, _ = _run(["review-packet", "build", "--changed=R-FOO-001",
                         "--repo-root=" + str(repo), "--format=json"], capsys)
    assert code == 0
    packet = json.loads(out)
    assert out.strip() == json.dumps(packet, indent=2, sort_keys=True)
    assert log.is_file() and "check_readiness" in log.read_text()

    vr = field(packet, "verification_results")
    assert isinstance(vr, dict) and vr
    assert "comp-foo" in vr
    assert vr["comp-foo"]["mutation_score"] == 0.92
    assert vr["comp-foo"]["overall"] == "pass"

    rr = field(packet, "residual_risk")
    assert isinstance(rr, list) and rr
    for entry in rr:
        assert isinstance(entry, dict)
        assert entry["component_id"]
        assert isinstance(entry["message"], str) and entry["message"].strip()
    assert any(e["component_id"] == "comp-foo" for e in rr)

    ex = field(packet, "exemption_changes")
    assert "sealed" in ex and "pinned_overrides" in ex
    assert isinstance(ex["sealed"], list)
    assert isinstance(ex["pinned_overrides"], list)


def test_space_separated_flags_and_changed_requirements(tmp_path, capsys):
    repo, _ = _make_repo(tmp_path / "repo")
    code, out, _ = _run(["review-packet", "build", "--changed", "R-FOO-001",
                         "--changed", "comp-foo", "--repo-root", str(repo),
                         "--format", "json"], capsys)
    assert code == 0
    packet = json.loads(out)
    assert field(packet, "changed_requirements") == ["R-FOO-001"]


def test_usage_errors_return_2(tmp_path, capsys):
    repo, _ = _make_repo(tmp_path / "repo")
    r = str(repo)
    cases = [
        ["review-packet", "build", "--repo-root=" + r],
        ["review-packet", "serve", "--changed=R-FOO-001"],
        ["review-packet"],
        ["review-packet", "build", "--repo-root=" + r, "--changed"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + r, "--format"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + r, "--format=bogus"],
    ]
    for argv in cases:
        code, _, _ = _run(argv, capsys)
        assert code == 2, argv


def test_check_readiness_value_error_returns_1(tmp_path, capsys):
    repo, _ = _make_repo(tmp_path / "repo_raise", mode="raise")
    code, _, _ = _run(["review-packet", "build", "--changed=R-FOO-001",
                       "--repo-root=" + str(repo)], capsys)
    assert code == 1


def test_sorted_keys_in_json_and_markdown(tmp_path, capsys):
    repo, _ = _make_repo(tmp_path / "repo_az", include_az=True)
    a_pat = re.compile(r'"a":\s*2\b')
    z_pat = re.compile(r'"z":\s*1\b')

    code, out, _ = _run(["review-packet", "build", "--changed=R-FOO-001",
                         "--repo-root=" + str(repo), "--format=json"], capsys)
    assert code == 0
    ma, mz = a_pat.search(out), z_pat.search(out)
    assert ma and mz
    assert ma.start() < mz.start()

    code, out, _ = _run(["review-packet", "build", "--changed=R-FOO-001",
                         "--repo-root=" + str(repo)], capsys)
    assert code == 0
    ma, mz = a_pat.search(out), z_pat.search(out)
    assert ma and mz
    assert ma.start() < mz.start()