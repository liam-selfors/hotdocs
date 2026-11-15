import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _read_log(path):
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _append_log(path, record):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _install_fakes(monkeypatch, tmp_path, report=None, failures_sequence=None):
    readiness_log = tmp_path / "check_readiness.log"
    feedback_log = tmp_path / "last_requirement_failures.log"
    failures_sequence = list(failures_sequence or [])

    def fake_check_readiness(
        repo_root, changed_ids=None, model=None, seed=0, llm_backend=None
    ):
        _append_log(
            readiness_log,
            {
                "repo_root": str(repo_root),
                "changed_ids": None if changed_ids is None else list(changed_ids),
                "model": model,
                "seed": seed,
                "seed_type": type(seed).__name__,
            },
        )
        return report

    def fake_last_requirement_failures(component_id, repo_root):
        index = len(_read_log(feedback_log))
        _append_log(
            feedback_log,
            {"component_id": component_id, "repo_root": str(repo_root)},
        )
        if index < len(failures_sequence):
            return list(failures_sequence[index])
        return []

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )
    return readiness_log, feedback_log


def test_verify_not_ready_text_with_changed_model_seed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-a": {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            }
        },
        "capabilities": {},
        "not_ready_reasons": ["comp-a: provenance miss"],
    }
    readiness_log, feedback_log = _install_fakes(monkeypatch, tmp_path, report=report)

    rc = provenance_tracker.main(
        [
            "verify",
            "--changed",
            "comp-a",
            "--changed=comp-b",
            "--model=m",
            "--seed",
            "3",
            f"--repo-root={tmp_path}",
        ]
    )
    out = capsys.readouterr().out

    assert rc == 1
    assert "not ready" in out
    assert "comp-a: provenance miss" in out

    calls = _read_log(readiness_log)
    assert len(calls) == 1
    call = calls[0]
    assert call["changed_ids"] == ["comp-a", "comp-b"]
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert call["seed_type"] == "int"
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()
    assert _read_log(feedback_log) == []


def test_verify_ready_json_without_changed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    readiness_log, feedback_log = _install_fakes(monkeypatch, tmp_path, report=report)

    rc = provenance_tracker.main(
        ["verify", "--format=json", "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(out)
    assert field(parsed, "ready") is True

    calls = _read_log(readiness_log)
    assert len(calls) == 1
    assert not calls[0]["changed_ids"]
    assert Path(calls[0]["repo_root"]).resolve() == tmp_path.resolve()
    assert _read_log(feedback_log) == []


def test_track_feedback_prints_failures_then_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    readiness_log, feedback_log = _install_fakes(
        monkeypatch,
        tmp_path,
        report=None,
        failures_sequence=[["R-A-001", "R-A-002"], []],
    )

    rc1 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out1 = capsys.readouterr().out
    assert rc1 == 0
    assert out1.strip() == "R-A-001,R-A-002"

    rc2 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out2 = capsys.readouterr().out
    assert rc2 == 0
    assert out2.strip() == ""

    calls = _read_log(feedback_log)
    assert len(calls) == 2
    assert all(c["component_id"] == "comp-a" for c in calls)
    assert _read_log(readiness_log) == []


@pytest.mark.parametrize(
    "argv",
    [
        ["verify", "--seed=x"],
        ["verify", "--format=bogus"],
        ["verify", "--bogus"],
        ["verify", "--model"],
        ["track", "feedback"],
        ["build"],
    ],
)
def test_usage_errors_return_2_and_call_nothing(tmp_path, monkeypatch, capsys, argv):
    monkeypatch.chdir(tmp_path)
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    readiness_log, feedback_log = _install_fakes(
        monkeypatch, tmp_path, report=report, failures_sequence=[["R-A-001"]]
    )

    rc = provenance_tracker.main(list(argv))
    capsys.readouterr()

    assert rc == 2
    assert _read_log(readiness_log) == []
    assert _read_log(feedback_log) == []