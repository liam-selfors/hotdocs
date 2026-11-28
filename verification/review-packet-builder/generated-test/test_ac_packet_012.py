# hotdocs-criterion: sha256:99fe295c93d20bf39a37ef616e89c0dd70329a321837ee8b82a49575199eadf2
import json
import re
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


VERIFICATION_RESULT = {"z": 1, "a": 2}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": dict(VERIFICATION_RESULT),
                "license_scan": {
                    "gate_version": "license_scanner@1.0.0",
                    "blocked": False,
                    "matches": [],
                },
                "secret_scan": {
                    "scope": "full",
                    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
                    "flagged": False,
                    "matches": [],
                    "allowed": [],
                    "unused_allowlist_entries": [],
                    "notified": False,
                    "notification_delivery_error": None,
                    "cache_hit": False,
                },
            }
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [],
    }


def _fake_tracker_source(log_path, raise_value_error):
    src = "from pathlib import Path\n\n"
    src += "LOG_PATH = " + repr(str(log_path)) + "\n\n"
    src += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    src += "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    src += "        fh.write(repr(changed_ids) + '\\n')\n"
    if raise_value_error:
        src += "    raise ValueError(" + repr(
            "P-ZERO-EDIT: capability needs a fresh run; pass --model") + ")\n"
    else:
        src += "    return " + repr(_verify_report()) + "\n"
    src += "\n"
    src += "def last_requirement_failures(component_id, repo_root):\n"
    src += "    return []\n"
    return src


def _make_repo(tmp_path, raise_value_error=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a fixture term.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — foo MUST return one.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\nfoo returns one.\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return 1\n")
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _fake_tracker_source(log_path, raise_value_error),
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — foo MUST return exactly one.\n",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "change R-FOO-001")

    return repo_root, log_path


@pytest.fixture
def repo(tmp_path):
    return _make_repo(tmp_path)


def _run(argv, capsys):
    capsys.readouterr()
    rc = review_packet_builder.main(argv)
    out = capsys.readouterr()
    return rc, out.out, out.err


def test_build_json_renders_real_content(repo, capsys):
    repo_root, log_path = repo
    rc, out, err = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root), "--format=json"],
        capsys,
    )
    assert rc == 0, err
    packet = json.loads(out)

    assert log_path.is_file(), "provenance-tracker fake was never called"

    verification_results = field(packet, "verification_results")
    assert isinstance(verification_results, dict)
    assert VERIFICATION_RESULT in list(verification_results.values())

    residual_risk = field(packet, "residual_risk")
    assert isinstance(residual_risk, list)
    for entry in residual_risk:
        assert isinstance(entry, dict)
        assert isinstance(entry["component_id"], str) and entry["component_id"]
        assert isinstance(entry["message"], str) and entry["message"]

    exemption_changes = field(packet, "exemption_changes")
    assert "sealed" in exemption_changes
    assert "pinned_overrides" in exemption_changes
    assert exemption_changes["sealed"] == []
    assert exemption_changes["pinned_overrides"] == []


def test_repeated_changed_space_separated(repo, capsys):
    repo_root, _ = repo
    rc, out, err = _run(
        ["review-packet", "build", "--changed", "R-FOO-001",
         "--changed", "comp-foo", "--repo-root", str(repo_root),
         "--format", "json"],
        capsys,
    )
    assert rc == 0, err
    packet = json.loads(out)
    assert field(packet, "changed_requirements") == ["R-FOO-001"]


def _usage_argvs(repo_root):
    root = str(repo_root)
    return [
        ["review-packet", "build", "--repo-root=" + root],
        ["review-packet", "serve", "--changed=R-FOO-001"],
        ["review-packet"],
        ["review-packet", "build", "--repo-root=" + root, "--changed"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root"],
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + root, "--format"],
    ]


@pytest.mark.parametrize("index", range(6))
def test_usage_errors_return_2(repo, capsys, index):
    repo_root, _ = repo
    argv = _usage_argvs(repo_root)[index]
    rc, _, _ = _run(argv, capsys)
    assert rc == 2


def test_bogus_format_returns_2(repo, capsys):
    repo_root, _ = repo
    rc, _, _ = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root), "--format=bogus"],
        capsys,
    )
    assert rc == 2


def test_check_readiness_value_error_returns_1(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path, raise_value_error=True)
    rc, _, _ = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root)],
        capsys,
    )
    assert rc == 1
    assert log_path.is_file(), "provenance-tracker fake was never called"


def _assert_a_before_z(text):
    a_match = re.search(r'"a"\s*:\s*2', text)
    z_match = re.search(r'"z"\s*:\s*1', text)
    assert a_match is not None, text
    assert z_match is not None, text
    assert a_match.start() < z_match.start(), text


def test_verification_result_keys_sorted_in_both_formats(repo, capsys):
    repo_root, _ = repo
    rc, out_json, err = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root), "--format=json"],
        capsys,
    )
    assert rc == 0, err
    _assert_a_before_z(out_json)

    rc, out_md, err = _run(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root)],
        capsys,
    )
    assert rc == 0, err
    _assert_a_before_z(out_md)