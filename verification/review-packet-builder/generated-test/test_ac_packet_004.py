import json
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-foo"

VERIFICATION_REPORT = {
    "component_id": COMPONENT_ID,
    "criteria": [
        {
            "id": "AC-FOO-001",
            "covers": "R-FOO-001",
            "kind": "compiled",
            "result": "pass",
        },
        {
            "id": "AC-FOO-002",
            "covers": "R-FOO-002",
            "kind": "compiled",
            "result": "fail",
            "failure_detail": {
                "message": "result.foo equals 5 failed",
                "expected": 5,
                "actual": 3,
            },
        },
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
    "interface_drift": False,
    "mutation_score": None,
    "overall": "fail",
}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": False,
    "components": {
        COMPONENT_ID: {
            "hit": True,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": {"blocked": False, "findings": []},
            "secret_scan": {"flagged": False, "findings": []},
        }
    },
    "capabilities": {},
    "not_ready_reasons": [
        "comp-foo: verification failed (overall=fail)",
    ],
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _build_fixture(repo_root: Path) -> Path:
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n\n"
        "# Foo\n\nA synthetic fixture component.\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nfoo() -> int\n```\n")
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — foo MUST return an int.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — foo MUST return 5.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven nothing\nWhen foo runs\nThen the result is an int\n```\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "```gherkin\nGiven nothing\nWhen foo runs\nThen the result equals 5\n```\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return 3\n")

    log_path = repo_root.parent / "tracker_invocations.log"
    tracker_src = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "REPORT = " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fn': 'check_readiness', 'changed_ids': "
        "list(changed_ids) if changed_ids is not None else None}) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_src,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial fixture")
    return log_path


def _criteria_by_id(report):
    criteria = field(report, "criteria")
    out = {}
    for c in criteria:
        out[field(c, "id")] = c
    return out


def test_verification_results_show_each_criterion_individually(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = _build_fixture(repo_root)

    packet = review_packet_builder.build_review_packet(
        [COMPONENT_ID, "R-FOO-002"], repo_root
    )

    # The stand-in tracker was actually consulted.
    assert log_path.exists()
    calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert any(c["fn"] == "check_readiness" for c in calls)

    verification_results = field(packet, "verification_results")
    assert COMPONENT_ID in verification_results
    report = verification_results[COMPONENT_ID]

    # Not merely an aggregate verdict: the per-criterion breakdown is present.
    assert not isinstance(report, (str, bool))
    criteria = field(report, "criteria")
    assert len(list(criteria)) == 2

    by_id = _criteria_by_id(report)
    assert set(by_id) == {"AC-FOO-001", "AC-FOO-002"}
    assert field(by_id["AC-FOO-001"], "result") == "pass"
    assert field(by_id["AC-FOO-002"], "result") == "fail"
    assert field(by_id["AC-FOO-001"], "covers") == "R-FOO-001"
    assert field(by_id["AC-FOO-002"], "covers") == "R-FOO-002"