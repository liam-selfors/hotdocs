# hotdocs-criterion: sha256:188a119339d67614acaae38ca9fd8f340ad71bb5436c93edafe54eb9d4c5329d
import inspect
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _report(ready, reasons, scope):
    return {
        "scope": scope,
        "ready": ready,
        "components": {},
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": list(reasons),
    }


def _install_fakes(monkeypatch, readiness_result=None, feedback_results=None):
    calls = {"check_readiness": [], "last_requirement_failures": []}
    feedback_queue = list(feedback_results or [])

    def fake_check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        calls["check_readiness"].append(
            {
                "repo_root": repo_root,
                "changed_ids": changed_ids,
                "model": model,
                "seed": seed,
                "llm_backend": llm_backend,
            }
        )
        if readiness_result is None:
            return _report(True, [], "whole-corpus")
        return readiness_result

    def fake_last_requirement_failures(component_id, repo_root):
        calls["last_requirement_failures"].append(
            {"component_id": component_id, "repo_root": repo_root}
        )
        if feedback_queue:
            return feedback_queue.pop(0)
        return []

    # Sanity: fakes match the documented signatures.
    assert list(inspect.signature(fake_check_readiness).parameters) == [
        "repo_root", "changed_ids", "model", "seed", "llm_backend",
    ]
    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )
    return calls


def test_verify_not_ready_with_changed_model_seed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(
        monkeypatch,
        readiness_result=_report(False, ["comp-a: provenance miss"], "blast-radius"),
    )
    rc = provenance_tracker.main(
        [
            "verify",
            "--changed", "comp-a",
            "--changed=comp-b",
            "--model=m",
            "--seed", "3",
            "--repo-root=" + str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 1
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    assert "not ready" in lines
    assert "comp-a: provenance miss" in lines
    assert len(calls["check_readiness"]) == 1
    call = calls["check_readiness"][0]
    assert list(call["changed_ids"]) == ["comp-a", "comp-b"]
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert isinstance(call["seed"], int)
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()
    assert calls["last_requirement_failures"] == []


def test_verify_ready_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(
        monkeypatch, readiness_result=_report(True, [], "whole-corpus")
    )
    rc = provenance_tracker.main(
        ["verify", "--format=json", "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert rc == 0
    doc = json.loads(out)
    assert field(doc, "ready") is True
    assert len(calls["check_readiness"]) == 1
    call = calls["check_readiness"][0]
    assert not call["changed_ids"]
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()
    assert calls["last_requirement_failures"] == []


def test_track_feedback_prints_failures_then_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(
        monkeypatch, feedback_results=[["R-A-001", "R-A-002"], []]
    )
    rc1 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out1 = capsys.readouterr().out
    rc2 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out2 = capsys.readouterr().out
    assert rc1 == 0
    assert rc2 == 0
    assert out1.strip() == "R-A-001,R-A-002"
    assert out2.strip() == ""
    assert len(calls["last_requirement_failures"]) == 2
    assert all(c["component_id"] == "comp-a" for c in calls["last_requirement_failures"])
    assert calls["check_readiness"] == []


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
def test_usage_errors_return_2_and_call_nothing(argv, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(monkeypatch, feedback_results=[["R-A-001"]])
    rc = provenance_tracker.main(list(argv))
    captured = capsys.readouterr()
    assert rc == 2
    assert calls["check_readiness"] == []
    assert calls["last_requirement_failures"] == []
    assert "Traceback" not in captured.err