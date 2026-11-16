import review_packet_builder

import json
import subprocess
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A synthetic fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do the thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When it runs\n"
        "Then the thing happens\n"
        "```\n",
    )
    _write(comp_dir / "constraints.md", "No constraints.\n")

    verification_report = {
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
        "mutation_score": 0.92,
        "overall": "pass",
    }
    verify_report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report,
                "license_scan": {"blocked": False, "matches": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }

    tracker_src = (
        "import json\n"
        "\n"
        f"_LOG_PATH = {str(log_path)!r}\n"
        f"_REPORT = {verify_report!r}\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fn': 'check_readiness', 'changed_ids': list(changed_ids) if changed_ids is not None else None}) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
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
    return repo_root, log_path


def test_residual_risk_includes_mutation_score_below_one_despite_pass(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], Path(repo_root)
    )

    # The provenance-tracker stand-in must actually have been consulted.
    assert log_path.exists(), "provenance-tracker stand-in check_readiness was never called"
    calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert any(c["fn"] == "check_readiness" for c in calls)

    residual_risk = field(packet, "residual_risk")
    assert isinstance(residual_risk, (list, tuple))

    matching = [
        entry for entry in residual_risk
        if not isinstance(entry, str) and field(entry, "component_id") == "comp-foo"
    ]
    assert matching, (
        f"residual_risk has no entry for comp-foo despite mutation_score 0.92 < 1.0 "
        f"with overall=pass: {residual_risk!r}"
    )

    messages = [field(entry, "message") for entry in matching]
    assert all(isinstance(m, str) and m.strip() for m in messages)
    assert any(
        ("mutation" in m.lower()) or ("0.92" in m) for m in messages
    ), f"no residual_risk message for comp-foo describes the mutation_score finding: {messages!r}"

    # Every residual_risk entry is an object, never a bare string.
    for entry in residual_risk:
        assert not isinstance(entry, str)