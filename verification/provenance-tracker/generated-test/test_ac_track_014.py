# hotdocs-criterion: sha256:b18a8bd80c5c6b8ec59f01f3c1e9eecf94f258179a9c91019dffd13032091eb2
import inspect
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _reference_check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return None


def _reference_last_requirement_failures(component_id, repo_root):
    return None


def _bind(reference, args, kwargs):
    bound = inspect.signature(reference).bind(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def _run_main(argv):
    try:
        return provenance_tracker.main(argv)
    except SystemExit as exc:
        code = exc.code
        return code


class Recorder:
    def __init__(self):
        self.readiness_calls = []
        self.feedback_calls = []


def _install(monkeypatch, report=None, feedback_results=None):
    rec = Recorder()
    results = list(feedback_results or [])

    def fake_check_readiness(*args, **kwargs):
        rec.readiness_calls.append(_bind(_reference_check_readiness, args, kwargs))
        return report

    def fake_last_requirement_failures(*args, **kwargs):
        rec.feedback_calls.append(_bind(_reference_last_requirement_failures, args, kwargs))
        if results:
            return results.pop(0)
        return []

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )
    return rec


def test_verify_not_ready_text_passes_changed_model_seed(monkeypatch, tmp_path, capsys):
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
    rec = _install(monkeypatch, report=report)

    code = _run_main(
        [
            "verify",
            "--changed",
            "comp-a",
            "--changed=comp-b",
            "--model=m",
            "--seed",
            "3",
            "--repo-root=" + str(tmp_path),
        ]
    )
    out = capsys.readouterr().out

    assert code == 1
    lines = [line.strip() for line in out.splitlines()]
    assert "not ready" in lines
    assert "comp-a: provenance miss" in lines

    assert len(rec.readiness_calls) == 1
    call = rec.readiness_calls[0]
    assert list(call["changed_ids"]) == ["comp-a", "comp-b"]
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert not isinstance(call["seed"], bool)
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()
    assert rec.feedback_calls == []


def test_verify_ready_json_without_changed(monkeypatch, tmp_path, capsys):
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    rec = _install(monkeypatch, report=report)

    code = _run_main(["verify", "--format=json", "--repo-root", str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 0
    parsed = json.loads(out)
    assert field(parsed, "ready") is True

    assert len(rec.readiness_calls) == 1
    call = rec.readiness_calls[0]
    assert not call["changed_ids"]
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()
    assert rec.feedback_calls == []


def test_track_feedback_prints_failures_then_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    rec = _install(monkeypatch, feedback_results=[["R-A-001", "R-A-002"], []])

    code1 = _run_main(["track", "feedback", "comp-a"])
    out1 = capsys.readouterr().out
    code2 = _run_main(["track", "feedback", "comp-a"])
    out2 = capsys.readouterr().out

    assert code1 == 0
    assert code2 == 0
    assert out1.strip() == "R-A-001,R-A-002"
    assert out2.strip() == ""

    assert len(rec.feedback_calls) == 2
    for call in rec.feedback_calls:
        assert call["component_id"] == "comp-a"
    assert rec.readiness_calls == []


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
def test_usage_errors_return_2_without_calling_fakes(monkeypatch, tmp_path, capsys, argv):
    monkeypatch.chdir(tmp_path)
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    rec = _install(monkeypatch, report=report, feedback_results=[["R-X-001"]])

    code = _run_main(list(argv))
    capsys.readouterr()

    assert code == 2
    assert rec.readiness_calls == []
    assert rec.feedback_calls == []