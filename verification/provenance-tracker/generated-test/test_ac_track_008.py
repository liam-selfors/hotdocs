# hotdocs-criterion: sha256:d2667979964f64a81533ca645f2cec9a5f4322b9d2c5c470bd0d9a7c9e92e226
"""AC-TRACK-008: last_requirement_failures reads the most recent AttemptRecord's
requirement_results and drops R-ids whose non-pass covering criteria all have
failure_origin "test" or "environment"."""

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class AttrDict(dict):
    """A plain dict that also exposes its keys as attributes, so a writer
    reading either dict items or attributes sees the same values."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _generation_result():
    return AttrDict(
        component_id="comp-foo",
        model="claude-sonnet-5",
        prompt_version="v1",
        files=[],
        model_call_error=None,
    )


def _verification_report(criteria, requirement_results):
    return AttrDict(
        component_id="comp-foo",
        criteria=[AttrDict(c) for c in criteria],
        requirement_results=dict(requirement_results),
        interface_drift=False,
        mutation_score=None,
        mutation_error=None,
        assets=[],
        overall="fail",
    )


def _write(repo_root, criteria, requirement_results):
    record = provenance_tracker.write_attempt_record(
        "comp-foo",
        _generation_result(),
        _verification_report(criteria, requirement_results),
        "sha256:" + "0" * 64,
        repo_root,
    )
    assert field(record, "component_id") == "comp-foo"
    return record


def test_plain_requirement_results_failures(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
         "failure_origin": "implementation"},
    ]
    _write(repo_root, criteria, {"R-FOO-001": "pass", "R-FOO-002": "fail"})

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)
    assert list(result) == ["R-FOO-002"]


def test_test_origin_failure_is_dropped(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "fail",
         "failure_origin": "test"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "fail",
         "failure_origin": "implementation"},
    ]
    _write(repo_root, criteria, {"R-FOO-001": "fail", "R-FOO-002": "fail"})

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)
    assert list(result) == ["R-FOO-002"]


def test_pass_plus_environment_dropped_absent_origin_kept(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-003", "covers": "R-FOO-001", "kind": "compiled", "result": "fail",
         "failure_origin": "environment"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "fail",
         "failure_origin": "test"},
        {"id": "AC-FOO-004", "covers": "R-FOO-002", "kind": "llm-judge", "result": "fail",
         "rationale": "does not hold"},
    ]
    _write(repo_root, criteria, {"R-FOO-001": "fail", "R-FOO-002": "fail"})

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)
    assert list(result) == ["R-FOO-002"]