import provenance_tracker

from pathlib import Path


class _DualAccess(dict):
    """A plain dict that also exposes its keys as attributes, so the target
    may read a caller-supplied value either way."""

    def __getattr__(self, name):
        try:
            value = self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        return value


def _dual(value):
    if isinstance(value, dict):
        return _DualAccess({k: _dual(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_dual(v) for v in value]
    return value


def _generation_result():
    return _dual(
        {
            "component_id": "comp-foo",
            "model_call_error": None,
            "files": [
                {"path": "gen/foo/foo.py", "content": "def foo():\n    return 1\n"}
            ],
        }
    )


def _verification_report():
    return _dual(
        {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                },
                {
                    "id": "AC-FOO-002",
                    "covers": "R-FOO-002",
                    "kind": "compiled",
                    "result": "fail",
                    "failure_detail": {
                        "message": "result.foo equals 5 failed",
                        "expected": 5,
                        "actual": 3,
                    },
                },
            ],
            "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "fail",
        }
    )


def test_last_requirement_failures_returns_exactly_failing_rids(tmp_path):
    repo_root = Path(tmp_path)

    provenance_tracker.write_attempt_record(
        "comp-foo",
        _generation_result(),
        _verification_report(),
        "sha256:0123456789abcdef",
        repo_root,
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts"
    assert attempts_dir.exists(), "write_attempt_record must write under .hotdocs/attempts/"

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

    assert isinstance(result, list)
    assert result == ["R-FOO-002"]