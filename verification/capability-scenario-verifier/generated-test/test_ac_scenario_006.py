import json
import textwrap
from pathlib import Path

import pytest

import capability_scenario_verifier


def _dual(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_fixture(repo_root: Path, log_path: Path) -> None:
    (repo_root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "components" / "foo-bar").mkdir(parents=True, exist_ok=True)
    (repo_root / "gen" / "test-author").mkdir(parents=True, exist_ok=True)
    (repo_root / "gen" / "foo-bar").mkdir(parents=True, exist_ok=True)

    capability_doc = textwrap.dedent(
        """\
        ---
        id: P-X
        title: Capability X
        status: ratified
        owners: [test-owner]
        last_ratified_commit: "0000000"
        ---

        ### CS-X-001

        Covers: P-X
        Kind: generated-test

        ```gherkin
        Given a widget
        When it is used
        Then it works
        ```
        """
    )
    (repo_root / "specs" / "product" / "p_x.md").write_text(capability_doc)

    component_doc = textwrap.dedent(
        """\
        ---
        id: comp-foo-bar
        title: Foo Bar
        status: ratified
        owners: [test-owner]
        last_ratified_commit: "0000000"
        sealed: false
        realizes: [P-X]
        ---

        Foo Bar component.
        """
    )
    (repo_root / "specs" / "components" / "foo-bar" / "component.md").write_text(component_doc)

    (repo_root / "gen" / "foo-bar" / "foo_bar.py").write_text(
        "# placeholder realizing component code\n"
    )

    log_literal = repr(str(log_path))
    test_author_src = textwrap.dedent(
        f"""\
        def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
            def _get(obj, key, default=None):
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            criterion_id = _get(bundle, "criterion_id")
            with open({log_literal}, "a", encoding="utf-8") as f:
                f.write(str(criterion_id) + "\\n")

            return {{
                "model_call_error": None,
                "file": {{
                    "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                    "content": "def test_x():\\n    assert True\\n",
                }},
            }}
        """
    )
    (repo_root / "gen" / "test-author" / "test_author.py").write_text(test_author_src)


def test_fresh_run_writes_record_and_is_then_a_hit(tmp_path):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()
    log_path = tmp_path / "author_test_calls_1.log"
    _write_fixture(repo_root, log_path)

    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=2
    )

    assert _dual(result, "hit") is False

    report = _dual(result, "capability_scenario_report")
    cap_report = _dual(report, "P-X")
    assert _dual(cap_report, "overall") == "pass"

    assert log_path.exists()
    log_lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    assert log_lines == ["CS-X-001"]

    provenance_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert provenance_path.exists()
    record = json.loads(provenance_path.read_text())

    assert set(record.keys()) == {
        "capability_id",
        "gate_version",
        "content_hash",
        "realizing_components",
        "capability_scenario_report",
        "model",
        "seed",
    }
    assert record["capability_id"] == "P-X"
    assert record["model"] == "m"
    assert record["seed"] == 2
    assert record["realizing_components"] == ["comp-foo-bar"]
    assert record["capability_scenario_report"]["P-X"]["overall"] == "pass"
    assert isinstance(record["content_hash"], str) and record["content_hash"]
    assert isinstance(record["gate_version"], str) and record["gate_version"]

    check_result = capability_scenario_verifier.check_capability_provenance(
        "P-X", repo_root
    )
    assert _dual(check_result, "hit") is True


def test_missing_model_on_a_miss_raises_before_any_side_effect(tmp_path):
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    log_path = tmp_path / "author_test_calls_2.log"
    _write_fixture(repo_root, log_path)

    with pytest.raises(capability_scenario_verifier.ModelRequiredError):
        capability_scenario_verifier.run_capability_gates("P-X", repo_root)

    assert not log_path.exists()

    provenance_path = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    assert not provenance_path.exists()