# hotdocs-criterion: sha256:4e0a2b46be8216badc608c96f241166d21cd246a36655505dfd48cc274c31b0d
import json
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "overall": "pass",
        "z": 1,
        "a": 2,
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(),
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


def _make_repo(root, raise_value_error=False):
    root.mkdir(parents=True, exist_ok=True)
    _write(
        root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [tester]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(
        root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do the foo thing.\n",
    )
    _write(
        root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )
    _write(root / "legacy" / "foo" / "foo.py", "X = 1\n")

    if raise_value_error:
        body = (
            "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
            "    raise ValueError("
            + repr("P-FOO needs a fresh run but no --model was given")
            + ")\n"
        )
    else:
        body = (
            "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
            "    return "
            + repr(_verify_report())
            + "\n"
        )
    body += (
        "\n\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(root / "gen" / "provenance-tracker" / "provenance_tracker.py", body)

    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _run(argv):
    try:
        code = review_packet_builder.main(argv)
    except SystemExit as exc:
        code = exc.code
    return code


@pytest.fixture
def repo(tmp_path):
    return _make_repo(tmp_path / "repo")


@pytest.fixture
def failing_repo(tmp_path):
    return _make_repo(tmp_path / "failing", raise_value_error=True)


def _non_empty(value):
    if value is None:
        return False
    if isinstance(value, (dict, list, str)):
        return len(value) > 0
    return True


def test_build_json_returns_0_with_real_content(repo, capsys):
    code = _run(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    packet = json.loads(out)
    assert out.strip() == json.dumps(packet, indent=2, sort_keys=True).strip()

    vr = field(packet, "verification_results")
    assert isinstance(vr, dict)
    assert _non_empty(vr)
    assert "comp-foo" in vr
    assert _non_empty(vr["comp-foo"])

    rr = field(packet, "residual_risk")
    assert isinstance(rr, list)
    assert len(rr) >= 1
    for entry in rr:
        assert isinstance(entry, dict)
        assert _non_empty(entry.get("component_id"))
        assert isinstance(entry.get("message"), str) and entry["message"].strip()

    ex = field(packet, "exemption_changes")
    assert isinstance(ex, dict)
    assert "sealed" in ex
    assert "pinned_overrides" in ex
    assert isinstance(ex["sealed"], list)
    assert isinstance(ex["pinned_overrides"], list)


def test_separate_value_flags_and_repeated_changed(repo, capsys):
    code = _run(
        [
            "review-packet", "build",
            "--changed", "R-FOO-001",
            "--changed", "comp-foo",
            "--repo-root", str(repo),
            "--format", "json",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    packet = json.loads(out)
    assert field(packet, "changed_requirements") == ["R-FOO-001"]


@pytest.mark.parametrize(
    "case",
    [
        "no_changed",
        "serve",
        "no_subcommand",
        "bare_changed",
        "bare_repo_root",
        "bare_format",
    ],
)
def test_usage_errors_return_2(repo, case, capsys):
    argvs = {
        "no_changed": ["review-packet", "build", "--repo-root=" + str(repo)],
        "serve": ["review-packet", "serve", "--changed=R-FOO-001"],
        "no_subcommand": ["review-packet"],
        "bare_changed": ["review-packet", "build", "--repo-root=" + str(repo), "--changed"],
        "bare_repo_root": ["review-packet", "build", "--changed=R-FOO-001", "--repo-root"],
        "bare_format": [
            "review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo), "--format"
        ],
    }
    code = _run(argvs[case])
    capsys.readouterr()
    assert code == 2


def test_invalid_format_returns_2(repo, capsys):
    code = _run(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo), "--format=bogus"]
    )
    capsys.readouterr()
    assert code == 2


def test_check_readiness_value_error_returns_1(failing_repo, capsys):
    code = _run(["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(failing_repo)])
    capsys.readouterr()
    assert code == 1


def _verification_section(markdown):
    heading = "## Verification Results"
    start = markdown.find(heading)
    assert start != -1, "markdown has no '## Verification Results' section"
    body = markdown[start + len(heading):]
    nxt = body.find("\n## ")
    return body if nxt == -1 else body[:nxt]


def test_sorted_keys_in_json_and_markdown(repo, capsys):
    code = _run(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    packet = json.loads(out)
    assert "comp-foo" in packet["verification_results"]
    assert '"a": 2' in out
    assert '"z": 1' in out
    assert out.index('"a": 2') < out.index('"z": 1')

    code = _run(["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo)])
    md = capsys.readouterr().out
    assert code == 0
    section = _verification_section(md)
    assert '"a"' in section
    assert '"z"' in section
    assert section.index('"a"') < section.index('"z"')