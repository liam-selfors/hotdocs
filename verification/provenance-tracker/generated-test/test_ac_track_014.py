# hotdocs-criterion: sha256:ee0766f22f42e460576ac2cce222f0d911837f1099fddcd34125211c79d18fc3
import inspect
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _bind_check_readiness(args, kwargs):
    def sig(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        pass

    bound = inspect.signature(sig).bind(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def _bind_last_failures(args, kwargs):
    def sig(component_id, repo_root):
        pass

    bound = inspect.signature(sig).bind(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def _install_fakes(monkeypatch, report, failures_sequence=None):
    readiness_calls = []
    failure_calls = []
    seq = list(failures_sequence or [])

    def fake_check_readiness(*args, **kwargs):
        readiness_calls.append(_bind_check_readiness(args, kwargs))
        return report

    def fake_last_requirement_failures(*args, **kwargs):
        failure_calls.append(_bind_last_failures(args, kwargs))
        if seq:
            return seq.pop(0)
        return []

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )
    return readiness_calls, failure_calls


def _not_ready_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-a": {
                "hit": False,
                "reason": "no manifest",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            }
        },
        "capabilities": {},
        "secret_scan": {"flagged": False, "matches": []},
        "not_ready_reasons": ["comp-a: provenance miss"],
    }


def _ready_report():
    return {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [],
    }


def test_verify_not_ready_text(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    readiness_calls, failure_calls = _install_fakes(monkeypatch, _not_ready_report())

    rc = provenance_tracker.main(
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
    assert rc == 1
    lines = [line.strip() for line in out.splitlines()]
    assert "not ready" in lines
    assert "comp-a: provenance miss" in lines

    assert len(readiness_calls) == 1
    call = readiness_calls[0]
    assert list(call["changed_ids"]) == ["comp-a", "comp-b"]
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert not isinstance(call["seed"], bool)
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()
    assert failure_calls == []


def test_verify_ready_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    readiness_calls, failure_calls = _install_fakes(monkeypatch, _ready_report())

    rc = provenance_tracker.main(
        ["verify", "--format=json", "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert rc == 0
    doc = json.loads(out)
    assert field(doc, "ready") is True

    assert len(readiness_calls) == 1
    call = readiness_calls[0]
    assert not call["changed_ids"]
    assert Path(call["repo_root"]).resolve() == tmp_path.resolve()
    assert failure_calls == []


def test_track_feedback_prints_failures_then_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    readiness_calls, failure_calls = _install_fakes(
        monkeypatch, _ready_report(), [["R-A-001", "R-A-002"], []]
    )

    rc1 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out1 = capsys.readouterr().out
    assert rc1 == 0
    assert out1.strip() == "R-A-001,R-A-002"

    rc2 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out2 = capsys.readouterr().out
    assert rc2 == 0
    assert out2.strip() == ""

    assert len(failure_calls) == 2
    assert all(c["component_id"] == "comp-a" for c in failure_calls)
    assert readiness_calls == []


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
def test_usage_errors_return_2_without_calling_fakes(tmp_path, monkeypatch, capsys, argv):
    monkeypatch.chdir(tmp_path)
    readiness_calls, failure_calls = _install_fakes(monkeypatch, _ready_report())

    rc = provenance_tracker.main(list(argv))
    captured = capsys.readouterr()
    assert rc == 2
    assert "Traceback" not in captured.err
    assert readiness_calls == []
    assert failure_calls == []