import provenance_tracker

from pathlib import Path


class _DualDict(dict):
    """A plain JSON-serializable dict that also exposes its keys as attributes,
    so it satisfies either dict-style or attribute-style reading."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _dual(value):
    if isinstance(value, dict):
        return _DualDict({k: _dual(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_dual(v) for v in value]
    return value


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_last_requirement_failures_returns_only_failing_rids(tmp_path):
    repo_root = Path(tmp_path)

    generation_result = _dual(
        {
            "component_id": "comp-foo",
            "model_call_error": None,
            "files": [],
        }
    )
    verification_report = _dual(
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
                        "message": "x equals 1 failed",
                        "expected": 1,
                        "actual": 2,
                    },
                },
            ],
            "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "fail",
        }
    )

    record = provenance_tracker.write_attempt_record(
        "comp-foo",
        generation_result,
        verification_report,
        "sha256:" + "a" * 64,
        repo_root,
    )

    # Precondition: the most recent record for comp-foo has a non-null
    # verification carrying the given flat requirement_results mapping.
    verification = _field(record, "verification")
    assert verification is not None
    assert dict(_field(verification, "requirement_results")) == {
        "R-FOO-001": "pass",
        "R-FOO-002": "fail",
    }
    assert (repo_root / ".hotdocs" / "attempts").is_dir()

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

    assert isinstance(result, list)
    assert result == ["R-FOO-002"]