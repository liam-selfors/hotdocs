# hotdocs-criterion: sha256:e4d6f466655ef93c225e99c872632f23f7c9ab1029ddc8f89b0685e147bc542c
import json
import re
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_REPORT = {
    "z": 1,
    "a": 2,
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.92,
    "mutation_error": None,
    "assets": [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": "sha256:" + "0" * 64,
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "drivers": [],
    "overall": "pass",
}

LICENSE_SCAN = {
    "gate_version": "license_scanner@1.0.0",
    "blocked": False,
    "flagged": False,
    "matches": [],
    "cache_hit": False,
}

SECRET_SCAN = {
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

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": True,
    "components": {
        "comp-foo": {
            "hit": True,
            "reason": None,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": LICENSE_SCAN,
            "secret_scan": SECRET_SCAN,
        }
    },
    "capabilities": {},
    "secret_scan": None,
    "not_ready_reasons": [],
}


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo), check=True, capture_output=True,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make_repo(root, raise_value_error=False):
    repo = root / "repo"
    repo.mkdir(parents=True)
    log = root / "tracker_calls.log"

    _write(
        repo / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        repo / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — foo MUST do bar.\n",
    )
    _write(
        repo / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\nfoo does bar.\n",
    )
    _write(repo / "legacy" / "foo" / "foo.py", "def foo():\n    return 1\n")

    src = (
        "import copy\n"
        "REPORT = " + repr(VERIFY_REPORT) + "\n"
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
    )
    if raise_value_error:
        src += (
            "    raise ValueError(" + repr("P-FOO-CAP: capability needs a fresh run; pass --model") + ")\n"
        )
    else:
        src += (
            "    report = copy.deepcopy(REPORT)\n"
            "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
            "    return report\n"
        )
    src += (
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo / "gen" / "provenance-tracker" / "provenance_tracker.py", src)

    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo, log


def _run(argv, capsys):
    capsys.readouterr()
    code = review_packet_builder.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_build_json_renders_real_content(tmp_path, capsys):
    repo, log = make_repo(tmp_path)
    code, out, err = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo), "--format=json"],
        capsys,
    )
    assert code == 0, err
    packet = json.loads(out)
    assert log.is_file() and "check_readiness" in log.read_text()

    vr = packet["verification_results"]
    assert isinstance(vr, dict)
    assert "comp-foo" in vr
    assert vr["comp-foo"]["mutation_score"] == 0.92
    assert vr["comp-foo"]["overall"] == "pass"
    assert vr["comp-foo"]["z"] == 1
    assert vr["comp-foo"]["a"] == 2

    rr = packet["residual_risk"]
    assert isinstance(rr, list)
    assert len(rr) >= 1
    for entry in rr:
        assert isinstance(entry, dict)
        assert isinstance(entry["component_id"], str)
        assert isinstance(entry["message"], str) and entry["message"].strip()
    assert any(entry["component_id"] == "comp-foo" for entry in rr)

    ex = packet["exemption_changes"]
    assert "sealed" in ex
    assert "pinned_overrides" in ex
    assert isinstance(ex["sealed"], list)
    assert isinstance(ex["pinned_overrides"], list)


def test_build_json_repeated_space_separated_changed(tmp_path, capsys):
    repo, _ = make_repo(tmp_path)
    code, out, err = _run(
        ["review-packet", "build", "--changed", "R-FOO-001", "--changed", "comp-foo",
         "--repo-root", str(repo), "--format", "json"],
        capsys,
    )
    assert code == 0, err
    packet = json.loads(out)
    assert packet["changed_requirements"] == ["R-FOO-001"]


def test_usage_errors_return_2(tmp_path, capsys):
    repo, _ = make_repo(tmp_path)
    argvs = [
        ["review-packet", "build", "--repo-root=" + str(repo)],
        ["review-packet", "serve", "--changed=R-FOO-001"],
        ["review-packet"],
        ["review-packet", "build", "--repo-root=" + str(repo), "--changed"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root"],
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo), "--format"],
    ]
    for argv in argvs:
        code, out, err = _run(argv, capsys)
        assert code == 2, (argv, out, err)


def test_bogus_format_returns_2(tmp_path, capsys):
    repo, _ = make_repo(tmp_path)
    code, out, err = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo), "--format=bogus"],
        capsys,
    )
    assert code == 2, (out, err)


def test_check_readiness_value_error_returns_1(tmp_path, capsys):
    repo, log = make_repo(tmp_path, raise_value_error=True)
    code, out, err = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo)],
        capsys,
    )
    assert code == 1, (out, err)


A_RE = re.compile(r'"a"\s*:\s*2')
Z_RE = re.compile(r'"z"\s*:\s*1')


def test_verification_result_keys_sorted_in_json_and_markdown(tmp_path, capsys):
    repo, _ = make_repo(tmp_path)

    code, out, err = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo), "--format=json"],
        capsys,
    )
    assert code == 0, err
    a = A_RE.search(out)
    z = Z_RE.search(out)
    assert a is not None and z is not None, out
    assert a.start() < z.start()

    code, out, err = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo)],
        capsys,
    )
    assert code == 0, err
    assert "## Verification Results" in out
    start = out.index("## Verification Results")
    rest = out[start + len("## Verification Results"):]
    nxt = re.search(r"(?m)^## ", rest)
    section = rest[: nxt.start()] if nxt else rest
    a = A_RE.search(section)
    z = Z_RE.search(section)
    assert a is not None and z is not None, section
    assert a.start() < z.start()