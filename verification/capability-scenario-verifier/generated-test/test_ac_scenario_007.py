import json
from pathlib import Path
from textwrap import dedent

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_record(repo_root: Path) -> dict:
    record_path = (
        repo_root / "verification" / "capabilities" / "P-ZERO-EDIT" / ".provenance.json"
    )
    return json.loads(record_path.read_text(encoding="utf-8"))


def _author_call_count(log_path: Path) -> int:
    if not log_path.exists():
        return 0
    return len(
        [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    )


def _setup_repo(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "product" / "zero-edit.md",
        dedent(
            """\
            ---
            id: P-ZERO-EDIT
            title: Zero Edit Capability
            status: ratified
            owners: [alice]
            last_ratified_commit: deadbeef
            ---

            ### CS-ZERO-EDIT-001

            Covers: P-ZERO-EDIT
            Kind: generated-test

            ```gherkin
            Given a cache manager
            When it stores a value
            Then it can retrieve the value
            ```
            """
        ),
    )
    _write(
        repo_root / "specs" / "components" / "cache-manager" / "component.md",
        dedent(
            """\
            ---
            id: comp-cache-manager
            title: Cache Manager
            status: ratified
            owners: [alice]
            realizes: [P-ZERO-EDIT]
            sealed: false
            last_ratified_commit: deadbeef
            ---

            Cache manager component.
            """
        ),
    )
    _write(
        repo_root / "gen" / "cache-manager" / "cache_manager.py",
        "def handle():\n    return 'cache-manager'\n",
    )
    _write(
        repo_root / "specs" / "components" / "other-thing" / "component.md",
        dedent(
            """\
            ---
            id: comp-other-thing
            title: Other Thing
            status: ratified
            owners: [alice]
            realizes: []
            sealed: false
            last_ratified_commit: deadbeef
            ---

            Other thing component.
            """
        ),
    )
    _write(
        repo_root / "gen" / "other-thing" / "other_thing.py",
        "def handle():\n    return 'other-thing'\n",
    )
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        dedent(
            """\
            import os


            def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
                if isinstance(bundle, dict):
                    criterion_id = bundle.get('criterion_id')
                else:
                    criterion_id = getattr(bundle, 'criterion_id', None)
                log_path = os.environ.get('AC_SCENARIO_007_AUTHOR_LOG')
                if log_path:
                    with open(log_path, 'a', encoding='utf-8') as handle:
                        handle.write(str(criterion_id) + '\\n')
                safe_id = str(criterion_id).lower().replace('-', '_')
                return {
                    'model_call_error': None,
                    'file': {
                        'path': 'verification/capabilities/P-ZERO-EDIT/generated-test/test_' + safe_id + '.py',
                        'content': 'def test_x():\\n    assert True\\n',
                    },
                }
            """
        ),
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        dedent(
            """\
            def complete(prompt, model, backend=None, **params):
                return {'text': 'ok', 'model_call_error': None}
            """
        ),
    )


def test_ac_scenario_007_content_hash_sensitivity(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    _setup_repo(repo_root)

    log_path = tmp_path / "author_invocations.log"
    monkeypatch.setenv("AC_SCENARIO_007_AUTHOR_LOG", str(log_path))

    capability_id = "P-ZERO-EDIT"

    # Establish a committed record via a first (necessarily-miss) run.
    first_result = capability_scenario_verifier.run_capability_gates(
        capability_id, repo_root, model="fake-model", seed=0
    )
    assert _get(first_result, "hit") is False

    baseline_check = capability_scenario_verifier.check_capability_provenance(
        capability_id, repo_root
    )
    assert _get(baseline_check, "hit") is True
    baseline_record = _read_record(repo_root)
    hash0 = baseline_record["content_hash"]
    calls_after_baseline = _author_call_count(log_path)

    # Given a committed record that is a hit, when one byte of a realizing
    # component's code file changes (no spec file touched), hit goes false.
    code_file = repo_root / "gen" / "cache-manager" / "cache_manager.py"
    original_code = code_file.read_text(encoding="utf-8")
    code_file.write_text(original_code + "# one extra byte\n", encoding="utf-8")

    check_after_code_change = capability_scenario_verifier.check_capability_provenance(
        capability_id, repo_root
    )
    assert _get(check_after_code_change, "hit") is False

    # A call to run_capability_gates after that change re-runs the scenarios
    # and the record's content_hash differs from before.
    second_result = capability_scenario_verifier.run_capability_gates(
        capability_id, repo_root, model="fake-model", seed=0
    )
    assert _get(second_result, "hit") is False
    calls_after_rerun = _author_call_count(log_path)
    assert calls_after_rerun == calls_after_baseline + 1

    record_after_rerun = _read_record(repo_root)
    hash1 = record_after_rerun["content_hash"]
    assert hash1 != hash0

    # Restore the code file and re-establish a baseline hit matching hash0.
    code_file.write_text(original_code, encoding="utf-8")
    capability_scenario_verifier.run_capability_gates(
        capability_id, repo_root, model="fake-model", seed=0
    )
    restored_record = _read_record(repo_root)
    assert restored_record["content_hash"] == hash0
    restored_check = capability_scenario_verifier.check_capability_provenance(
        capability_id, repo_root
    )
    assert _get(restored_check, "hit") is True

    # Given the same hit, when the capability's own specs/product file
    # changes, hit goes false.
    product_file = repo_root / "specs" / "product" / "zero-edit.md"
    original_product = product_file.read_text(encoding="utf-8")
    product_file.write_text(original_product + "\n<!-- edited -->\n", encoding="utf-8")

    check_after_product_change = capability_scenario_verifier.check_capability_provenance(
        capability_id, repo_root
    )
    assert _get(check_after_product_change, "hit") is False

    product_file.write_text(original_product, encoding="utf-8")
    check_after_product_restore = capability_scenario_verifier.check_capability_provenance(
        capability_id, repo_root
    )
    assert _get(check_after_product_restore, "hit") is True

    # Given the same hit, a file change in a component that does not
    # realize the capability still gives hit true.
    other_file = repo_root / "gen" / "other-thing" / "other_thing.py"
    original_other = other_file.read_text(encoding="utf-8")
    other_file.write_text(original_other + "# irrelevant change\n", encoding="utf-8")

    check_after_other_change = capability_scenario_verifier.check_capability_provenance(
        capability_id, repo_root
    )
    assert _get(check_after_other_change, "hit") is True

    # A __pycache__ file appearing under a realizing component's code
    # directory still gives hit true.
    pycache_file = (
        repo_root / "gen" / "cache-manager" / "__pycache__" / "cache_manager.cpython-311.pyc"
    )
    pycache_file.parent.mkdir(parents=True, exist_ok=True)
    pycache_file.write_bytes(b"\x00\x01fakebytecode")

    check_after_pycache = capability_scenario_verifier.check_capability_provenance(
        capability_id, repo_root
    )
    assert _get(check_after_pycache, "hit") is True