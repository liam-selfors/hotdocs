import inspect
import json
from pathlib import Path

import pytest

import provenance_tracker


def _reference_check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    raise AssertionError("reference signature only")


def _reference_last_requirement_failures(component_id, repo_root):
    raise AssertionError("reference signature only")


_CHECK_SIG = inspect.signature(_reference_check_readiness)
_LAST_SIG = inspect.signature(_reference_last_requirement_failures)


def _run_main(argv):
    try:
        return provenance_tracker.main(argv)
    except SystemExit as exc:  # tolerate argparse-style exits, but require the code
        code = exc.code
        if code is None:
            return 0
        return code


def _install_fakes(monkeypatch, readiness_reports, failure_lists):
    calls = {"check_readiness": [], "last_requirement_failures": []}
    readiness_iter = iter(readiness_reports)
    failures_iter = iter(failure_lists)

    def fake_check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        bound = _CHECK_SIG.bind(repo_root, changed_ids, model, seed, llm_backend)
        bound.apply_defaults()
        calls["check_readiness"].append(dict(bound.arguments))
        return next(readiness_iter)

    def fake_last_requirement_failures(component_id, repo_root):
        bound = _LAST_SIG.bind(component_id, repo_root)
        bound.apply_defaults()
        calls["last_requirement_failures"].append(dict(bound.arguments))
        return list(next(failures_iter))

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )
    return calls


def _not_ready_report():
    return {
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


def _ready_report():
    return {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }


def test_verify_not_ready_text_passes_changed_model_seed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(monkeypatch, [_not_ready_report()], [])

    rc = _run_main(
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
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    assert "comp-a: provenance miss" in lines

    assert len(calls["check_readiness"]) == 1
    assert calls["last_requirement_failures"] == []
    call = calls["check_readiness"][0]
    assert list(call["changed_ids"]) == ["comp-a", "comp-b"]
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert not isinstance(call["seed"], bool)
    assert isinstance(call["seed"], int)
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()


def test_verify_ready_json_without_changed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(monkeypatch, [_ready_report()], [])

    rc = _run_main(["verify", "--format=json", "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(out)
    assert parsed["ready"] is True

    assert len(calls["check_readiness"]) == 1
    assert calls["last_requirement_failures"] == []
    call = calls["check_readiness"][0]
    assert not call["changed_ids"]
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()


def test_track_feedback_prints_failures_then_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(monkeypatch, [], [["R-A-001", "R-A-002"], []])

    rc1 = _run_main(["track", "feedback", "comp-a"])
    out1 = capsys.readouterr().out
    rc2 = _run_main(["track", "feedback", "comp-a"])
    out2 = capsys.readouterr().out

    assert rc1 == 0
    assert rc2 == 0
    assert out1.strip() == "R-A-001,R-A-002"
    assert out2.strip() == ""

    assert calls["check_readiness"] == []
    assert len(calls["last_requirement_failures"]) == 2
    for call in calls["last_requirement_failures"]:
        assert call["component_id"] == "comp-a"


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
def test_usage_errors_return_2_without_calling_fakes(argv, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(
        monkeypatch, [_ready_report(), _ready_report()], [["R-A-001"], ["R-A-001"]]
    )

    rc = _run_main(list(argv))
    capsys.readouterr()

    assert rc == 2
    assert calls["check_readiness"] == []
    assert calls["last_requirement_failures"] == []