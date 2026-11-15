import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _run_main(argv):
    try:
        return provenance_tracker.main(argv)
    except SystemExit as exc:  # tolerate sys.exit-style returns
        code = exc.code
        return 0 if code is None else code


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _append_log(log_path, record):
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _install_fakes(monkeypatch, log_path, report, feedback_sequence):
    def fake_check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        _append_log(
            log_path,
            {
                "fn": "check_readiness",
                "repo_root": str(repo_root),
                "changed_ids": list(changed_ids) if changed_ids is not None else None,
                "model": model,
                "seed": seed,
                "seed_type": type(seed).__name__,
            },
        )
        return report

    def fake_last_requirement_failures(component_id, repo_root):
        prior = [r for r in _read_log(log_path) if r["fn"] == "last_requirement_failures"]
        _append_log(
            log_path,
            {
                "fn": "last_requirement_failures",
                "component_id": component_id,
                "repo_root": str(repo_root),
            },
        )
        idx = len(prior)
        if idx < len(feedback_sequence):
            return list(feedback_sequence[idx])
        return []

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )


def test_verify_text_not_ready_passes_changed_model_seed(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.chdir(tmp_path)
    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {"comp-a": {"hit": False, "verification_report": None,
                                  "license_scan": None, "secret_scan": None}},
        "capabilities": {},
        "not_ready_reasons": ["comp-a: provenance miss"],
    }
    _install_fakes(monkeypatch, log_path, report, [])

    code = _run_main(
        [
            "verify",
            "--changed",
            "comp-a",
            "--changed=comp-b",
            "--model=m",
            "--seed",
            "3",
            f"--repo-root={repo_root}",
        ]
    )
    out = capsys.readouterr().out

    assert code == 1
    assert "not ready" in out
    assert "comp-a: provenance miss" in out

    calls = [r for r in _read_log(log_path) if r["fn"] == "check_readiness"]
    assert len(calls) == 1
    call = calls[0]
    assert call["changed_ids"] == ["comp-a", "comp-b"]
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert call["seed_type"] == "int"


def test_verify_json_ready_whole_corpus(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.chdir(tmp_path)
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _install_fakes(monkeypatch, log_path, report, [])

    code = _run_main(["verify", "--format=json", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out

    assert code == 0
    parsed = json.loads(out)
    assert field(parsed, "ready") is True

    calls = [r for r in _read_log(log_path) if r["fn"] == "check_readiness"]
    assert len(calls) == 1
    assert not calls[0]["changed_ids"]


def test_track_feedback_prints_failures_then_nothing(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.chdir(tmp_path)
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _install_fakes(monkeypatch, log_path, report, [["R-A-001", "R-A-002"], []])

    code1 = _run_main(["track", "feedback", "comp-a"])
    out1 = capsys.readouterr().out
    code2 = _run_main(["track", "feedback", "comp-a"])
    out2 = capsys.readouterr().out

    assert code1 == 0
    assert code2 == 0
    assert out1.strip() == "R-A-001,R-A-002"
    assert out2.strip() == ""

    calls = [r for r in _read_log(log_path) if r["fn"] == "last_requirement_failures"]
    assert len(calls) == 2
    assert all(c["component_id"] == "comp-a" for c in calls)


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
    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.chdir(tmp_path)
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _install_fakes(monkeypatch, log_path, report, [["R-A-001"]])

    code = _run_main(list(argv))
    capsys.readouterr()

    assert code == 2
    assert _read_log(log_path) == []