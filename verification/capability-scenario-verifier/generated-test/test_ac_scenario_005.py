import json
import pathlib
import shutil

import pytest

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _find_real_repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for ancestor in [here] + list(here.parents):
        if (ancestor / "pipeline" / "criterion-compiler").is_dir():
            return ancestor
    raise RuntimeError(
        "could not locate the real repository root (no ancestor of this "
        "test file contains pipeline/criterion-compiler)"
    )


def _snapshot(repo_root: pathlib.Path) -> dict:
    snap = {}
    for path in repo_root.rglob("*"):
        if path.is_file():
            snap[str(path.relative_to(repo_root))] = path.read_bytes()
    return snap


_CAPABILITY_MD = """---
id: P-ZERO-EDIT
---

### CS-ZERO-EDIT-001

Covers: P-ZERO-EDIT
Kind: generated-test

```gherkin
Given a thing
When it happens
Then it works
```
"""


_FAKE_TEST_AUTHOR_TEMPLATE = '''import json


def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    criterion_id = _get(bundle, "criterion_id")
    with open("__LOG_PATH__", "a") as f:
        f.write(json.dumps({"fn": "author_test", "criterion_id": criterion_id}) + "\\n")

    slug = criterion_id.lower().replace("-", "_")
    return {
        "model_call_error": None,
        "file": {
            "path": "verification/capabilities/P-ZERO-EDIT/generated-test/test_" + slug + ".py",
            "content": "def test_x():\\n    assert True\\n",
        },
    }
'''


_FAKE_LLM_ENDPOINT_TEMPLATE = '''import json


def complete(prompt, model, backend=None, **params):
    with open("__LOG_PATH__", "a") as f:
        f.write(json.dumps({"fn": "complete"}) + "\\n")
    return {"text": "ok", "model_call_error": None}
'''


def _fake_test_author_src(log_path: str) -> str:
    return _FAKE_TEST_AUTHOR_TEMPLATE.replace("__LOG_PATH__", log_path)


def _fake_llm_endpoint_src(log_path: str) -> str:
    return _FAKE_LLM_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", log_path)


def _build_repo(
    tmp_path: pathlib.Path,
    name: str,
    real_repo_root: pathlib.Path,
    log_path: pathlib.Path,
) -> pathlib.Path:
    repo_root = tmp_path / name
    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / "zero-edit.md").write_text(_CAPABILITY_MD)

    shutil.copytree(
        real_repo_root / "pipeline" / "criterion-compiler",
        repo_root / "pipeline" / "criterion-compiler",
    )

    gen_test_author = repo_root / "gen" / "test-author"
    gen_test_author.mkdir(parents=True)
    (gen_test_author / "test_author.py").write_text(
        _fake_test_author_src(str(log_path))
    )

    gen_llm_endpoint = repo_root / "gen" / "llm-endpoint"
    gen_llm_endpoint.mkdir(parents=True)
    (gen_llm_endpoint / "llm_endpoint.py").write_text(
        _fake_llm_endpoint_src(str(log_path))
    )

    return repo_root


def test_hit_is_pure_read_and_run_capability_gates_reuses_it_unchanged(tmp_path):
    real_repo_root = _find_real_repo_root()
    log_path = tmp_path / "calls.log"
    log_path.write_text("")

    repo_root = _build_repo(tmp_path, "main", real_repo_root, log_path)

    # Derive a committed record whose gate_version/content_hash match the
    # current ones by letting the component itself write one, rather than
    # guessing its internal hash formula.
    fresh = capability_scenario_verifier.run_capability_gates(
        "P-ZERO-EDIT", repo_root, "seed-model"
    )
    assert _get(fresh, "hit") is False
    assert _get(fresh, "capability_scenario_report") is not None
    assert log_path.read_text().strip() != ""

    record_path = (
        repo_root
        / "verification"
        / "capabilities"
        / "P-ZERO-EDIT"
        / ".provenance.json"
    )
    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert record["capability_scenario_report"] == _get(
        fresh, "capability_scenario_report"
    )

    calls_after_fresh_run = log_path.read_text()

    check_result = capability_scenario_verifier.check_capability_provenance(
        "P-ZERO-EDIT", repo_root
    )
    assert _get(check_result, "hit") is True
    assert (
        _get(check_result, "capability_scenario_report")
        == record["capability_scenario_report"]
    )
    assert log_path.read_text() == calls_after_fresh_run

    snapshot_before = _snapshot(repo_root)

    gates_with_model = capability_scenario_verifier.run_capability_gates(
        "P-ZERO-EDIT", repo_root, "m"
    )
    assert _get(gates_with_model, "hit") == _get(check_result, "hit")
    assert _get(gates_with_model, "capability_scenario_report") == _get(
        check_result, "capability_scenario_report"
    )
    assert log_path.read_text() == calls_after_fresh_run
    assert _snapshot(repo_root) == snapshot_before

    gates_with_none_model = capability_scenario_verifier.run_capability_gates(
        "P-ZERO-EDIT", repo_root, None
    )
    assert _get(gates_with_none_model, "hit") == _get(check_result, "hit")
    assert _get(gates_with_none_model, "capability_scenario_report") == _get(
        check_result, "capability_scenario_report"
    )
    assert log_path.read_text() == calls_after_fresh_run
    assert _snapshot(repo_root) == snapshot_before


def test_check_capability_provenance_misses_on_absent_invalid_or_stale_record(
    tmp_path,
):
    real_repo_root = _find_real_repo_root()
    log_path = tmp_path / "unused-calls.log"
    log_path.write_text("")

    # No record at all.
    repo_no_record = _build_repo(tmp_path, "no-record", real_repo_root, log_path)
    result_no_record = capability_scenario_verifier.check_capability_provenance(
        "P-ZERO-EDIT", repo_no_record
    )
    assert _get(result_no_record, "hit") is False
    assert _get(result_no_record, "capability_scenario_report") is None

    # Record present but not valid JSON.
    repo_invalid = _build_repo(tmp_path, "invalid-json", real_repo_root, log_path)
    record_dir = repo_invalid / "verification" / "capabilities" / "P-ZERO-EDIT"
    record_dir.mkdir(parents=True)
    (record_dir / ".provenance.json").write_text("{this is not valid json")
    result_invalid = capability_scenario_verifier.check_capability_provenance(
        "P-ZERO-EDIT", repo_invalid
    )
    assert _get(result_invalid, "hit") is False
    assert _get(result_invalid, "capability_scenario_report") is None

    # Record present, valid JSON, but a stale gate_version.
    repo_stale = _build_repo(tmp_path, "stale-gate-version", real_repo_root, log_path)
    record_dir2 = repo_stale / "verification" / "capabilities" / "P-ZERO-EDIT"
    record_dir2.mkdir(parents=True)
    stale_record = {
        "capability_id": "P-ZERO-EDIT",
        "gate_version": "capability_scenario_verifier@0.0.1-stale",
        "content_hash": "sha256:" + "0" * 64,
        "realizing_components": [],
        "capability_scenario_report": {
            "P-ZERO-EDIT": {"overall": "pass", "scenarios": []}
        },
        "model": "m",
        "seed": 0,
    }
    (record_dir2 / ".provenance.json").write_text(json.dumps(stale_record))
    result_stale = capability_scenario_verifier.check_capability_provenance(
        "P-ZERO-EDIT", repo_stale
    )
    assert _get(result_stale, "hit") is False
    assert _get(result_stale, "capability_scenario_report") is None


def test_unknown_capability_raises_from_both_functions(tmp_path):
    real_repo_root = _find_real_repo_root()
    log_path = tmp_path / "unknown-calls.log"
    log_path.write_text("")

    repo_root = _build_repo(tmp_path, "unknown-capability", real_repo_root, log_path)

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance(
            "P-UNKNOWN", repo_root
        )

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates(
            "P-UNKNOWN", repo_root, model="m"
        )