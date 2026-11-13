import json
import os
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


CAP_ID = "P-ZERO-EDIT"

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


def _plain(value):
    """Convert a report-ish value into plain JSON-compatible data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "__dict__"):
        return {k: _plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


def _normalize(result):
    return {
        "hit": field(result, "hit"),
        "capability_scenario_report": _plain(field(result, "capability_scenario_report")),
    }


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_TEST_AUTHOR = '''\
import json

_LOG = {log!r}


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"fn": "author_test", "criterion_id": bundle["criterion_id"], "model": model}}) + "\\n")
    criterion_id = bundle["criterion_id"]
    fname = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    return {{
        "component_id": "comp-zero-edit-impl",
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {{
            "path": "verification/capabilities/P-ZERO-EDIT/generated-test/" + fname,
            "content": "def test_x():\\n    assert True\\n",
        }},
        "model_call_error": None,
    }}
'''

FAKE_LLM_ENDPOINT = '''\
import json

_LOG = {log!r}


def complete(prompt, model, *, backend=None, **params):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"fn": "complete", "model": model}}) + "\\n")
    return {{
        "text": "pass",
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }}
'''


def _build_repo(tmp_path: Path):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    repo_root.mkdir()
    log_dir.mkdir()
    author_log = log_dir / "test_author_calls.jsonl"
    endpoint_log = log_dir / "llm_endpoint_calls.jsonl"

    # Capability spec
    _write(
        repo_root / "specs" / "product" / "zero-edit.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero edit\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# Zero edit\n"
        "\n"
        "### CS-ZERO-EDIT-001\n"
        "\n"
        "Covers: P-ZERO-EDIT\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an unchanged repository\n"
        "When verification runs\n"
        "Then nothing is regenerated\n"
        "```\n",
    )

    # Realizing component
    comp_dir = repo_root / "specs" / "components" / "zero-edit-impl"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-zero-edit-impl\n"
        "title: Zero edit impl\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-ZERO-EDIT]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Zero edit impl\n"
        "\n"
        "Realizes the zero-edit capability.\n",
    )
    _write(
        comp_dir / "requirements" / "R-ZEI-001.md",
        "**R-ZEI-001** — MUST do nothing when nothing changed.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-ZEI-001.md",
        "# AC-ZEI-001\n\nCovers: R-ZEI-001\nKind: generated-test\n\n"
        "```gherkin\nGiven nothing\nWhen nothing\nThen nothing\n```\n",
    )
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nnoop()\n```\n")
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "gen" / "zero-edit-impl" / "zero_edit_impl.py",
        "def noop():\n    return None\n",
    )

    # Fake dependencies
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        FAKE_TEST_AUTHOR.format(log=str(author_log)),
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        FAKE_LLM_ENDPOINT.format(log=str(endpoint_log)),
    )

    # Real compiler copied from the live repository
    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

    return repo_root, author_log, endpoint_log


def _record_path(repo_root: Path) -> Path:
    return repo_root / "verification" / "capabilities" / CAP_ID / ".provenance.json"


def _snapshot(root: Path):
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            st = p.stat()
            snap[str(p.relative_to(root))] = (st.st_mtime_ns, st.st_size, p.read_bytes())
    return snap


def _calls(log: Path):
    if not log.exists():
        return []
    return [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def seeded(tmp_path):
    repo_root, author_log, endpoint_log = _build_repo(tmp_path)

    # Seed a committed record whose content_hash is the current one, by a
    # real run against the fakes.
    capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    record_path = _record_path(repo_root)
    assert record_path.is_file(), "seeding run did not write the committed record"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION

    # Make the committed report a known passing one (content_hash untouched).
    record["capability_scenario_report"] = PASSING_REPORT
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    # Reset the fakes' invocation logs.
    for log in (author_log, endpoint_log):
        if log.exists():
            log.unlink()

    return repo_root, author_log, endpoint_log, record_path, record


def test_check_is_hit_and_carries_record_report(seeded):
    repo_root, _a, _e, _rp, record = seeded
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is True
    assert _plain(field(result, "capability_scenario_report")) == record["capability_scenario_report"]
    assert _plain(field(result, "capability_scenario_report")) == PASSING_REPORT


def test_run_on_hit_returns_check_result_untouched(seeded):
    repo_root, author_log, endpoint_log, _rp, record = seeded

    check = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(check, "hit") is True

    before = _snapshot(repo_root)

    result_m = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    result_none_default = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root)
    result_none_explicit = capability_scenario_verifier.run_capability_gates(
        CAP_ID, repo_root, None
    )
    result_none_kw = capability_scenario_verifier.run_capability_gates(
        CAP_ID, repo_root, model=None
    )

    after = _snapshot(repo_root)

    expected = _normalize(check)
    assert expected["hit"] is True
    assert expected["capability_scenario_report"] == record["capability_scenario_report"]

    for res in (result_m, result_none_default, result_none_explicit, result_none_kw):
        assert _normalize(res) == expected
        if isinstance(res, dict) and isinstance(check, dict):
            assert res == check

    # No fake module was called.
    assert _calls(author_log) == []
    assert _calls(endpoint_log) == []

    # Nothing under repo_root was written or modified.
    assert set(after) == set(before), (
        "files added/removed: %r" % (set(after) ^ set(before))
    )
    for rel, info in before.items():
        assert after[rel] == info, "file modified: %s" % rel


def test_check_miss_cases(seeded):
    repo_root, author_log, endpoint_log, record_path, record = seeded

    # A record that is not valid JSON.
    record_path.write_text("{ this is not json", encoding="utf-8")
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None

    # A record with a different gate_version.
    stale = dict(record)
    stale["gate_version"] = "capability_scenario_verifier@0.0.1-different"
    record_path.write_text(json.dumps(stale, indent=2), encoding="utf-8")
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None

    # No record at all.
    record_path.unlink()
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None

    # The check is a pure read: no fake was called.
    assert _calls(author_log) == []
    assert _calls(endpoint_log) == []


def test_unknown_capability_raises(tmp_path):
    repo_root, _author_log, _endpoint_log = _build_repo(tmp_path)
    unknown = "P-NOT-DECLARED-ANYWHERE"

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance(unknown, repo_root)

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates(unknown, repo_root, "m")