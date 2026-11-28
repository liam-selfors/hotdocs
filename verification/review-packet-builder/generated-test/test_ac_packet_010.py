# hotdocs-criterion: sha256:9fb7d1ab5a6397fb927221f60fe20c5a8ee1a0e8909c6c5e10bcb756f8ab83b5
import dataclasses
import json
import os
import subprocess
from pathlib import Path

import review_packet_builder


OLD_MARKER = "zqxOldGeneratedMarker7731"
MID_MARKER = "zqxMidGeneratedMarker4482"
NEW_MARKER = "zqxNewGeneratedMarker9054"
ALL_MARKERS = [OLD_MARKER, MID_MARKER, NEW_MARKER]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args),
        cwd=str(repo_root),
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _generated_code(marker, n):
    lines = ["# generated module " + marker + "\n", "\n"]
    for i in range(n):
        lines.append("def " + marker + "_func_" + str(i) + "(x):\n")
        lines.append("    value_" + marker + " = x * " + str(i + 1) + "\n")
        lines.append("    return value_" + marker + " + " + repr(marker) + ".__len__()\n")
        lines.append("\n")
    return "".join(lines)


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False, "matches": []},
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


def _stand_in_source():
    return (
        "REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _build_fixture(repo_root):
    _git(repo_root, "init", "-q")
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a fixture term.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    req = repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
    _write(req, "# R-FOO-001\n\n**R-FOO-001** \u2014 Foo MUST return one.\n")
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it returns one\n```\n",
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", _stand_in_source())
    code = repo_root / "gen" / "foo" / "foo.py"
    _write(code, _generated_code(OLD_MARKER, 30))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")

    # The PR: a spec change plus a substantial rewrite of the generated code.
    _write(req, "# R-FOO-001\n\n**R-FOO-001** \u2014 Foo MUST return two.\n")
    _write(code, _generated_code(MID_MARKER, 40))
    _write(repo_root / "gen" / "foo" / "helpers.py", _generated_code(MID_MARKER + "Helper", 10))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "change")

    # A further uncommitted substantial change, so any diff base sees generated-code churn.
    _write(code, _generated_code(NEW_MARKER, 50))


def _to_plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_plain(v) for v in value]
    if hasattr(value, "__dict__") and not isinstance(value, (str, bytes, int, float, bool)):
        return {k: _to_plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


def _assert_no_generated_diff(text):
    for marker in ALL_MARKERS:
        assert marker not in text, "generated-code content leaked into packet: " + marker
    for header in ("a/gen/foo/", "b/gen/foo/", "diff --git a/gen/"):
        assert header not in text, "generated-code diff header leaked into packet: " + header


def test_packet_contains_no_generated_code_diff(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    spec_diff = field(packet, "spec_diff")
    assert isinstance(spec_diff, str)
    _assert_no_generated_diff(spec_diff)

    plain = _to_plain(packet)
    _assert_no_generated_diff(json.dumps(plain, default=str))
    _assert_no_generated_diff(repr(packet))


def test_cli_output_contains_no_generated_code_diff(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    for fmt in ("json", "markdown"):
        code = review_packet_builder.main(
            [
                "review-packet",
                "build",
                "--changed=comp-foo",
                "--changed",
                "R-FOO-001",
                "--repo-root=" + str(repo_root),
                "--format=" + fmt,
            ]
        )
        captured = capsys.readouterr()
        assert code == 0, captured.err
        _assert_no_generated_diff(captured.out)
        if fmt == "json":
            json.loads(captured.out)