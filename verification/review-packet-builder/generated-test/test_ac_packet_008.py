import review_packet_builder

import os
import subprocess
import textwrap
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "provenance_tracker_calls.log"

    # Minimal synthetic component spec.
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        textwrap.dedent(
            """\
            ---
            id: comp-foo
            title: Foo
            status: draft
            owners: [alice]
            depends_on: []
            ---

            # Foo

            A synthetic fixture component.
            """
        ),
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do a thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a foo\nWhen it runs\nThen it does a thing\n```\n",
    )
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nfoo() -> None\n```\n")
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo():\n    return None\n")

    # provenance-tracker stand-in: overall "pass" but mutation_score < 1.0.
    stand_in = textwrap.dedent(
        """\
        LOG_PATH = %r


        def _log(line):
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(line + "\\n")


        def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
            _log("check_readiness")
            return {
                "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
                "ready": True,
                "components": {
                    "comp-foo": {
                        "hit": True,
                        "verification_report": {
                            "component_id": "comp-foo",
                            "criteria": [
                                {
                                    "id": "AC-FOO-001",
                                    "covers": "R-FOO-001",
                                    "kind": "generated-test",
                                    "result": "pass",
                                },
                            ],
                            "requirement_results": {"R-FOO-001": "pass"},
                            "interface_drift": False,
                            "mutation_score": 0.92,
                            "overall": "pass",
                        },
                        "license_scan": {"blocked": False, "findings": []},
                        "secret_scan": {"flagged": False, "findings": []},
                    },
                },
                "capabilities": {},
                "not_ready_reasons": [],
            }


        def last_requirement_failures(component_id, repo_root):
            _log("last_requirement_failures")
            return []
        """
    ) % (str(log_path),)
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", stand_in)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial fixture")

    return repo_root, log_path


def test_ac_packet_008_residual_risk_includes_mutation_score_below_one(tmp_path):
    repo_root, log_path = _build_fixture(tmp_path)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    # The stand-in provenance-tracker was actually consulted.
    assert log_path.exists(), "provenance-tracker stand-in was never invoked"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    residual_risk = field(packet, "residual_risk")
    assert isinstance(residual_risk, list), f"residual_risk must be a list, got {residual_risk!r}"

    matching = []
    for entry in residual_risk:
        assert not isinstance(entry, str), (
            f"residual_risk entries must be objects, never bare strings: {entry!r}"
        )
        if field(entry, "component_id") == "comp-foo":
            matching.append(entry)

    assert matching, (
        "residual_risk must include the comp-foo finding (mutation_score 0.92 < 1.0 "
        f"despite overall=pass); got {residual_risk!r}"
    )

    messages = [field(entry, "message") for entry in matching]
    assert any(
        isinstance(m, str) and m.strip() and ("mutation" in m.lower() or "0.92" in m)
        for m in messages
    ), f"residual_risk entry for comp-foo must describe the mutation_score finding; got {messages!r}"