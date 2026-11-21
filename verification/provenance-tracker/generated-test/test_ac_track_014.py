# hotdocs-criterion: sha256:5ebc8e2f67c4b0889d6927486fee6791f332b733167f4a55eded9f93f38140b3
import inspect
import json

import pytest

import provenance_tracker


def _check_readiness_ref(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    pass


def _last_requirement_failures_ref(component_id, repo_root):
    pass


def _bind(ref, args, kwargs):
    bound = inspect.signature(ref).bind(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


class Recorder:
    def __init__(self, monkeypatch, readiness_reports=None, feedback_results=None):
        self.readiness_calls = []
        self.feedback_calls = []
        self._readiness_reports = list(readiness_reports or [])
        self._feedback_results = list(feedback_results or [])

        def fake_check_readiness(*args, **kwargs):
            self.readiness_calls.append(_bind(_check_readiness_ref, args, kwargs))
            return self._readiness_reports.pop(0)

        def fake_last_requirement_failures(*args, **kwargs):
            self.feedback_calls.append(_bind(_last_requirement_failures_ref, args, kwargs))
            return self._feedback_results.pop(0)

        monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
        monkeypatch.setattr(
            provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
        )


def _report(scope, ready, reasons):
    return {
        "scope": scope,
        "ready": ready,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": list(reasons),
    }


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_verify_not_ready_text_with_changed_model_seed(monkeypatch, capsys, tmp_path):
    rec = Recorder(
        monkeypatch,
        readiness_reports=[
            _report("blast-radius", False, ["comp-a: provenance miss"])
        ],
    )
    code = provenance_tracker.main(
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
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    assert "not ready" in lines
    assert "comp-a: provenance miss" in lines
    assert len(rec.readiness_calls) == 1
    call = rec.readiness_calls[0]
    assert list(call["changed_ids"]) == ["comp-a", "comp-b"]
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert isinstance(call["seed"], int) and not isinstance(call["seed"], bool)
    assert rec.feedback_calls == []


def test_verify_ready_json_without_changed(monkeypatch, capsys, tmp_path):
    rec = Recorder(
        monkeypatch,
        readiness_reports=[_report("whole-corpus", True, [])],
    )
    code = provenance_tracker.main(
        ["verify", "--format=json", "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert field(doc, "ready") is True
    assert len(rec.readiness_calls) == 1
    assert not rec.readiness_calls[0]["changed_ids"]
    assert rec.feedback_calls == []


def test_track_feedback_prints_failures_then_nothing(monkeypatch, capsys):
    rec = Recorder(
        monkeypatch,
        feedback_results=[["R-A-001", "R-A-002"], []],
    )
    code1 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out1 = capsys.readouterr().out
    code2 = provenance_tracker.main(["track", "feedback", "comp-a"])
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
def test_usage_errors_return_2_and_call_nothing(monkeypatch, capsys, argv):
    rec = Recorder(
        monkeypatch,
        readiness_reports=[_report("whole-corpus", True, [])],
        feedback_results=[[]],
    )
    code = provenance_tracker.main(list(argv))
    captured = capsys.readouterr()
    assert code == 2
    assert rec.readiness_calls == []
    assert rec.feedback_calls == []
    assert "Traceback" not in captured.err