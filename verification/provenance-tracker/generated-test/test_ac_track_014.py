import json

import provenance_tracker


def test_verify_not_ready_with_changed_passes_through_args(monkeypatch, capsys, tmp_path):
    calls = []

    def fake_check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        calls.append(
            {
                "repo_root": repo_root,
                "changed_ids": changed_ids,
                "model": model,
                "seed": seed,
                "llm_backend": llm_backend,
            }
        )
        return {
            "scope": "blast-radius",
            "ready": False,
            "components": {"comp-a": {"hit": False}},
            "capabilities": {},
            "not_ready_reasons": ["comp-a: provenance miss"],
        }

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)

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
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-a", "comp-b"]
    assert calls[0]["model"] == "m"
    assert calls[0]["seed"] == 3


def test_verify_ready_json_with_no_changed(monkeypatch, capsys, tmp_path):
    calls = []

    def fake_check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        calls.append({"changed_ids": changed_ids})
        return {
            "scope": "whole-corpus",
            "ready": True,
            "components": {},
            "capabilities": {},
            "not_ready_reasons": [],
        }

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)

    rc = provenance_tracker.main(
        ["verify", "--format=json", "--repo-root", str(tmp_path)]
    )

    out = capsys.readouterr().out
    data = json.loads(out)

    assert rc == 0
    ready = data.get("ready") if isinstance(data, dict) else getattr(data, "ready", None)
    assert ready is True
    assert len(calls) == 1
    assert calls[0]["changed_ids"] in (None, [])


def test_track_feedback_prints_failures_then_nothing(monkeypatch, capsys):
    calls = []
    results = [["R-A-001", "R-A-002"], []]

    def fake_last_requirement_failures(component_id, repo_root):
        calls.append({"component_id": component_id, "repo_root": repo_root})
        return results.pop(0)

    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )

    rc1 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out1 = capsys.readouterr().out
    assert rc1 == 0
    assert out1.strip() == "R-A-001,R-A-002"

    rc2 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out2 = capsys.readouterr().out
    assert rc2 == 0
    assert out2.strip() == ""

    assert len(calls) == 2
    assert calls[0]["component_id"] == "comp-a"
    assert calls[1]["component_id"] == "comp-a"


def test_usage_errors_return_2_and_never_call_fakes(monkeypatch, capsys):
    check_calls = []
    feedback_calls = []

    def fake_check_readiness(*args, **kwargs):
        check_calls.append((args, kwargs))
        return {"ready": True, "not_ready_reasons": []}

    def fake_last_requirement_failures(*args, **kwargs):
        feedback_calls.append((args, kwargs))
        return []

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake_check_readiness)
    monkeypatch.setattr(
        provenance_tracker, "last_requirement_failures", fake_last_requirement_failures
    )

    bad_argvs = [
        ["verify", "--seed=x"],
        ["verify", "--format=bogus"],
        ["verify", "--bogus"],
        ["verify", "--model"],
        ["track", "feedback"],
        ["build"],
    ]

    for argv in bad_argvs:
        rc = provenance_tracker.main(argv)
        assert rc == 2, f"expected exit code 2 for {argv!r}, got {rc!r}"

    capsys.readouterr()

    assert check_calls == []
    assert feedback_calls == []