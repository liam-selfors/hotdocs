import json

import pytest

import provenance_tracker


def _patch_check_readiness(monkeypatch, responses):
    calls = []
    queue = list(responses)

    def fake(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        calls.append(
            {
                "repo_root": repo_root,
                "changed_ids": changed_ids,
                "model": model,
                "seed": seed,
                "llm_backend": llm_backend,
            }
        )
        return queue.pop(0)

    monkeypatch.setattr(provenance_tracker, "check_readiness", fake)
    return calls


def _patch_last_requirement_failures(monkeypatch, responses):
    calls = []
    queue = list(responses)

    def fake(component_id, repo_root):
        calls.append({"component_id": component_id, "repo_root": repo_root})
        return queue.pop(0)

    monkeypatch.setattr(provenance_tracker, "last_requirement_failures", fake)
    return calls


def test_verify_not_ready_with_changed_ids_model_and_seed(monkeypatch, tmp_path, capsys):
    repo_root = tmp_path

    readiness_calls = _patch_check_readiness(
        monkeypatch,
        [
            {
                "scope": "blast-radius",
                "ready": False,
                "components": {"comp-a": {"hit": False}},
                "capabilities": {},
                "not_ready_reasons": ["comp-a: provenance miss"],
            }
        ],
    )
    feedback_calls = _patch_last_requirement_failures(monkeypatch, [])

    exit_code = provenance_tracker.main(
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

    assert exit_code == 1
    assert "not ready" in out
    assert "comp-a: provenance miss" in out
    assert len(readiness_calls) == 1
    assert readiness_calls[0]["changed_ids"] == ["comp-a", "comp-b"]
    assert readiness_calls[0]["model"] == "m"
    assert readiness_calls[0]["seed"] == 3
    assert len(feedback_calls) == 0


def test_verify_ready_json_no_changed_ids(monkeypatch, tmp_path, capsys):
    repo_root = tmp_path

    readiness_calls = _patch_check_readiness(
        monkeypatch,
        [
            {
                "scope": "whole-corpus",
                "ready": True,
                "components": {},
                "capabilities": {},
                "not_ready_reasons": [],
            }
        ],
    )
    feedback_calls = _patch_last_requirement_failures(monkeypatch, [])

    exit_code = provenance_tracker.main(
        ["verify", "--format=json", "--repo-root", str(repo_root)]
    )

    out = capsys.readouterr().out
    payload = json.loads(out)

    assert exit_code == 0
    assert payload.get("ready") is True
    assert len(readiness_calls) == 1
    assert not readiness_calls[0]["changed_ids"]
    assert len(feedback_calls) == 0


def test_track_feedback_sequential_calls(monkeypatch, capsys):
    feedback_calls = _patch_last_requirement_failures(
        monkeypatch,
        [
            ["R-A-001", "R-A-002"],
            [],
        ],
    )
    readiness_calls = _patch_check_readiness(monkeypatch, [])

    exit_code_1 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out_1 = capsys.readouterr().out

    exit_code_2 = provenance_tracker.main(["track", "feedback", "comp-a"])
    out_2 = capsys.readouterr().out

    assert exit_code_1 == 0
    assert out_1.strip() == "R-A-001,R-A-002"
    assert exit_code_2 == 0
    assert out_2.strip() == ""
    assert len(feedback_calls) == 2
    assert len(readiness_calls) == 0


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
def test_usage_errors_never_call_fakes(monkeypatch, argv):
    readiness_calls = _patch_check_readiness(monkeypatch, [])
    feedback_calls = _patch_last_requirement_failures(monkeypatch, [])

    exit_code = provenance_tracker.main(argv)

    assert exit_code == 2
    assert len(readiness_calls) == 0
    assert len(feedback_calls) == 0