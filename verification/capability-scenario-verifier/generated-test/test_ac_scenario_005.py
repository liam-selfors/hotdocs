# hotdocs-criterion: sha256:e68f8244ae33b7adc245c86cd235f2a99bec3b05b19d2f5efb73b76c703344bc
import json
import os
from pathlib import Path

import pytest

import capability_scenario_verifier


CAP_ID = "P-ZERO-EDIT"
RECORD_REL = Path("verification") / "capabilities" / CAP_ID / ".provenance.json"
PASSING_REPORT = {
    CAP_ID: {
        "overall": "pass",
        "scenarios": [
            {"id": "CS-ZERO-EDIT-001", "kind": "generated-test", "result": "pass"}
        ],
    }
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(result):
    return {
        "hit": field(result, "hit"),
        "capability_scenario_report": field(result, "capability_scenario_report"),
    }


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Thing** - a thing.\n",
    )

    # A realizing, non-sealed component.
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "sealed: false\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** - MUST do nothing.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven nothing\nWhen noop is called\nThen it returns null\n```\n",
    )
    write(
        repo_root / "gen" / "foo" / "foo.py",
        "def noop():\n    return None\n",
    )

    # The capability.
    write(
        repo_root / "specs" / "product" / "zero-edit.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero Edit\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n\n"
        "# Zero Edit\n\n"
        "### CS-ZERO-EDIT-001\n\n"
        "Covers: P-ZERO-EDIT\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given an unchanged spec\n"
        "When verify runs\n"
        "Then nothing is regenerated\n"
        "```\n",
    )

    # Fake test-author, recording every call to a log outside repo_root.
    test_content = "def test_x():\n    assert True\n"
    test_path = "verification/capabilities/P-ZERO-EDIT/generated-test/test_cs_zero_edit_001.py"
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'generated_test@1.2.0'\n"
        "\n"
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('author_test ' + str(bundle['criterion_id']) + '\\n')\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': " + repr(test_path) + ", 'content': " + repr(test_content) + "},\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )

    # Fake llm-endpoint, recording every call to the same log.
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )

    return repo_root, log_path


def seed_committed_record(repo_root, log_path):
    """Produce a record carrying the current gate_version and content_hash,
    then set its report to a known passing one."""
    capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    record_path = repo_root / RECORD_REL
    assert record_path.is_file()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION
    record["capability_scenario_report"] = PASSING_REPORT
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    if log_path.exists():
        log_path.unlink()
    return record_path, record


def snapshot(root):
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            p = Path(dirpath) / d
            state[str(p.relative_to(root)) + "/"] = None
        for f in filenames:
            p = Path(dirpath) / f
            st = p.stat()
            state[str(p.relative_to(root))] = (p.read_bytes(), st.st_mtime_ns)
    return state


def test_current_record_is_a_hit_and_gates_reuse_it(tmp_path):
    repo_root, log_path = build_repo(tmp_path)
    record_path, record = seed_committed_record(repo_root, log_path)

    before = snapshot(repo_root)

    check = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(check, "hit") is True
    assert field(check, "capability_scenario_report") == record["capability_scenario_report"]
    assert field(check, "capability_scenario_report") == PASSING_REPORT

    gated = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    assert as_plain(gated) == as_plain(check)

    gated_none = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, None)
    assert as_plain(gated_none) == as_plain(check)

    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""

    after = snapshot(repo_root)
    assert after == before


def test_missing_unreadable_or_stale_record_is_a_miss(tmp_path):
    repo_root, log_path = build_repo(tmp_path)
    record_path, record = seed_committed_record(repo_root, log_path)

    # No record.
    record_path.unlink()
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None

    # Not valid JSON.
    record_path.write_text("{not json", encoding="utf-8")
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None

    # Different gate_version.
    stale = dict(record)
    stale["gate_version"] = "capability_scenario_verifier@0.0.1"
    record_path.write_text(json.dumps(stale), encoding="utf-8")
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None


def test_unknown_capability_raises_from_both(tmp_path):
    repo_root, log_path = build_repo(tmp_path)

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance("P-NOPE", repo_root)

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates("P-NOPE", repo_root, "m")