# hotdocs-criterion: sha256:c575b9ddf2cd8e7071d09427d167d4483b579cc8b4859da400dfc121c5f2d6c9
import json

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
        "not_ready_reasons": list(reasons),
    }


def _install_fakes(monkeypatch, readiness_result, failures_results):
    calls = {"check_readiness": [], "last_requirement_failures": []}
    remaining = list(failures_results)

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
        return readiness_result

    def fake_last_requirement_failures(component_id, repo_root):
        calls["last_requirement_failures"].append(
            {"component_id": component_id, "repo_root": repo_root}
        )
        if remaining:
            return list(remaining.pop(0))
        return []

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )
    return calls


def test_verify_not_ready_text(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(
        monkeypatch,
        _report(False, ["comp-a: provenance miss"], "blast-radius"),
        [],
    )
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
    assert "not ready" in out
    assert "comp-a: provenance miss" in out
    assert len(calls["check_readiness"]) == 1
    call = calls["check_readiness"][0]
    assert list(call["changed_ids"]) == ["comp-a", "comp-b"]
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert not isinstance(call["seed"], bool)
    assert calls["last_requirement_failures"] == []


def test_verify_ready_json(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(monkeypatch, _report(True, [], "whole-corpus"), [])
    rc = provenance_tracker.main(
        ["verify", "--format=json", "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "ready") is True
    assert len(calls["check_readiness"]) == 1
    assert not calls["check_readiness"][0]["changed_ids"]
    assert calls["last_requirement_failures"] == []


def test_track_feedback(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(
        monkeypatch,
        _report(True, [], "whole-corpus"),
        [["R-A-001", "R-A-002"], []],
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
    for c in calls["last_requirement_failures"]:
        assert c["component_id"] == "comp-a"
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
def test_usage_errors(monkeypatch, capsys, tmp_path, argv):
    monkeypatch.chdir(tmp_path)
    calls = _install_fakes(
        monkeypatch,
        _report(True, [], "whole-corpus"),
        [["R-A-001"]],
    )
    rc = provenance_tracker.main(list(argv))
    captured = capsys.readouterr()
    assert rc == 2
    assert "Traceback" not in captured.err
    assert calls["check_readiness"] == []
    assert calls["last_requirement_failures"] == []