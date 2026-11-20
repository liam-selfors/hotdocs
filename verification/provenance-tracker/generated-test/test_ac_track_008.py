# hotdocs-criterion: sha256:7fdb01ec58e02e677eddf525c8faebc8a650daaba802a79f12ad872d781e2151
import provenance_tracker

from pathlib import Path


class AttrDict(dict):
    """A dict that also exposes its keys as attributes, so it reads correctly
    whether the target uses dict access or attribute access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def wrap(value):
    if isinstance(value, dict):
        return AttrDict({k: wrap(v) for k, v in value.items()})
    if isinstance(value, list):
        return [wrap(v) for v in value]
    return value


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SPEC_HASH = "sha256:" + "0" * 64


def generation_result():
    return wrap({
        "component_id": "comp-foo",
        "files": [{"path": "gen/foo/foo.py", "content": "x = 1\n"}],
        "model_call_error": None,
    })


def verification_report(criteria, requirement_results, overall="fail"):
    return wrap({
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "a" * 64,
                    "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": overall,
    })


def record(repo_root, criteria, requirement_results):
    repo_root.mkdir(parents=True, exist_ok=True)
    provenance_tracker.write_attempt_record(
        "comp-foo",
        generation_result(),
        verification_report(criteria, requirement_results),
        SPEC_HASH,
        repo_root,
    )
    assert (repo_root / ".hotdocs" / "attempts" / "comp-foo").is_dir()


def test_plain_fail_is_returned(tmp_path):
    repo_root = tmp_path / "repo1"
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
         "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test",
         "result": "fail", "failure_origin": "implementation",
         "failure_detail": {"message": "m", "expected": 1, "actual": 2}},
    ]
    record(repo_root, criteria, {"R-FOO-001": "pass", "R-FOO-002": "fail"})
    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)
    assert list(result) == ["R-FOO-002"]


def test_test_origin_failure_is_left_out(tmp_path):
    repo_root = tmp_path / "repo2"
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
         "result": "fail", "failure_origin": "test",
         "failure_detail": {"message": "m", "expected": None, "actual": None}},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test",
         "result": "fail", "failure_origin": "implementation",
         "failure_detail": {"message": "m", "expected": 1, "actual": 2}},
    ]
    record(repo_root, criteria, {"R-FOO-001": "fail", "R-FOO-002": "fail"})
    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)
    assert list(result) == ["R-FOO-002"]


def test_pass_plus_environment_left_out_test_plus_absent_origin_kept(tmp_path):
    repo_root = tmp_path / "repo3"
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
         "result": "pass"},
        {"id": "AC-FOO-003", "covers": "R-FOO-001", "kind": "compiled",
         "result": "fail", "failure_origin": "environment",
         "failure_detail": {"message": "m", "expected": None, "actual": None}},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test",
         "result": "fail", "failure_origin": "test",
         "failure_detail": {"message": "m", "expected": None, "actual": None}},
        {"id": "AC-FOO-004", "covers": "R-FOO-002", "kind": "compiled",
         "result": "fail",
         "failure_detail": {"message": "m", "expected": 1, "actual": 2}},
    ]
    record(repo_root, criteria, {"R-FOO-001": "fail", "R-FOO-002": "fail"})
    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)
    assert list(result) == ["R-FOO-002"]