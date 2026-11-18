# hotdocs-criterion: sha256:c604d7f178c33aebfe09e849686a4c126b79dcd02a492d356f82673476368d55
from pathlib import Path

import provenance_tracker


class AttrDict(dict):
    """A dict that also exposes its keys as attributes, so the target may
    read it either way (dual dict-or-attribute access)."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self):
        return dict(self)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result(component_id):
    return AttrDict(
        component_id=component_id,
        model_call_error=None,
        files=[],
        model="anthropic:claude-sonnet-5",
        seed=0,
    )


def _write(repo_root, component_id, verification):
    record = provenance_tracker.write_attempt_record(
        component_id,
        _generation_result(component_id),
        verification,
        "sha256:" + "0" * 64,
        repo_root,
    )
    assert field(record, "verification") is not None
    return record


def test_returns_failing_requirement_ids(tmp_path):
    repo_root = Path(tmp_path) / "repo"
    repo_root.mkdir()
    verification = AttrDict(
        component_id="comp-foo",
        criteria=[
            AttrDict(id="AC-FOO-001", covers="R-FOO-001", kind="generated-test", result="pass"),
            AttrDict(
                id="AC-FOO-002",
                covers="R-FOO-002",
                kind="generated-test",
                result="fail",
                failure_origin="implementation",
            ),
        ],
        requirement_results={"R-FOO-001": "pass", "R-FOO-002": "fail"},
        interface_drift=False,
        mutation_score=None,
        mutation_error=None,
        overall="fail",
    )
    _write(repo_root, "comp-foo", verification)

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)
    assert list(result) == ["R-FOO-002"]


def test_excludes_requirement_whose_failures_all_have_test_origin(tmp_path):
    repo_root = Path(tmp_path) / "repo"
    repo_root.mkdir()
    verification = AttrDict(
        component_id="comp-foo",
        criteria=[
            AttrDict(
                id="AC-FOO-001",
                covers="R-FOO-001",
                kind="generated-test",
                result="fail",
                failure_origin="test",
            ),
            AttrDict(
                id="AC-FOO-002",
                covers="R-FOO-002",
                kind="generated-test",
                result="fail",
                failure_origin="implementation",
            ),
        ],
        requirement_results={"R-FOO-001": "fail", "R-FOO-002": "fail"},
        interface_drift=False,
        mutation_score=None,
        mutation_error=None,
        overall="fail",
    )
    _write(repo_root, "comp-foo", verification)

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)
    assert list(result) == ["R-FOO-002"]