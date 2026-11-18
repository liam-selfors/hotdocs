# hotdocs-criterion: sha256:e68f8244ae33b7adc245c86cd235f2a99bec3b05b19d2f5efb73b76c703344bc
import json
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


CAP_ID = "P-ZERO-EDIT"
SLUG = "zero-edit-thing"
RECORD_REL = Path("verification") / "capabilities" / CAP_ID / ".provenance.json"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root():
    gen = next(
        p
        for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    return gen.parent


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _fake_test_author_source(log_path):
    lines = [
        "LOG = " + repr(str(log_path)),
        "",
        "",
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):",
        "    with open(LOG, 'a') as f:",
        "        f.write('author_test\\n')",
        "    cid = bundle['criterion_id']",
        "    name = 'test_' + cid.lower().replace('-', '_') + '.py'",
        "    path = " + repr("verification/capabilities/" + CAP_ID + "/generated-test/") + " + name",
        "    content = " + repr("def test_x():\n    assert True\n"),
        "    return {",
        "        'component_id': bundle.get('component_id', " + repr(CAP_ID) + "),",
        "        'criterion_id': cid,",
        "        'model': model,",
        "        'seed': seed,",
        "        'prompt_version': 'v1',",
        "        'cache_hit': False,",
        "        'file': {'path': path, 'content': content},",
        "        'model_call_error': None,",
        "    }",
        "",
    ]
    return "\n".join(lines)


def _fake_llm_endpoint_source(log_path):
    lines = [
        "LOG = " + repr(str(log_path)),
        "",
        "",
        "def complete(prompt, model, backend=None, **params):",
        "    with open(LOG, 'a') as f:",
        "        f.write('complete\\n')",
        "    return {",
        "        'text': 'PASS',",
        "        'model': model,",
        "        'backend': 'fake',",
        "        'model_call_error': None,",
        "    }",
        "",
    ]
    return "\n".join(lines)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    # Product capability
    _write(
        repo_root / "specs" / "product" / "zero-edit.md",
        "---\n"
        "id: " + CAP_ID + "\n"
        "title: Zero edit\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# Zero edit\n"
        "\n"
        "### CS-ZERO-EDIT-001\n"
        "\n"
        "Covers: " + CAP_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a cached artifact\n"
        "When the pipeline runs\n"
        "Then no file is edited\n"
        "```\n",
    )

    # Realizing component
    comp_dir = repo_root / "specs" / "components" / SLUG
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-" + SLUG + "\n"
        "title: Zero edit thing\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: [" + CAP_ID + "]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Zero edit thing\n",
    )
    _write(
        comp_dir / "requirements" / "R-ZET-001.md",
        "**R-ZET-001** - MUST do nothing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-ZET-001.md",
        "# AC-ZET-001\n\nCovers: R-ZET-001\nKind: generated-test\n\n"
        "```gherkin\nGiven nothing\nWhen nothing happens\nThen nothing changes\n```\n",
    )
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nnoop()\n```\n")
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "gen" / SLUG / (SLUG.replace("-", "_") + ".py"),
        "def noop():\n    return None\n",
    )

    # Fake dependencies (flat-module shape)
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        _fake_test_author_source(log_path),
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        _fake_llm_endpoint_source(log_path),
    )

    # Real compiler copied from the live repository
    src = _tool_root() / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    return repo_root, log_path


def _prime(repo_root):
    """Produce a committed record whose gate_version/content_hash are current."""
    result = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    assert field(result, "hit") is False
    record_path = repo_root / RECORD_REL
    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert record["gate_version"] == capability_scenario_verifier.GATE_VERSION
    return record_path, record


def _snapshot(repo_root):
    snap = {}
    for p in sorted(repo_root.rglob("*")):
        if p.is_file():
            st = p.stat()
            snap[str(p.relative_to(repo_root))] = (p.read_bytes(), st.st_mtime_ns)
    return snap


def _calls(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def test_hit_returns_record_report_and_gates_reuse_it_without_side_effects(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    record_path, record = _prime(repo_root)

    passing_report = {
        CAP_ID: {
            "overall": "pass",
            "scenarios": [
                {"id": "CS-ZERO-EDIT-001", "kind": "generated-test", "result": "pass"}
            ],
        }
    }
    record["capability_scenario_report"] = passing_report
    record_path.write_text(json.dumps(record, indent=2))

    if log_path.exists():
        log_path.unlink()
    before = _snapshot(repo_root)

    check = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(check, "hit") is True
    assert field(check, "capability_scenario_report") == passing_report

    run_m = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, "m")
    assert field(run_m, "hit") == field(check, "hit")
    assert field(run_m, "capability_scenario_report") == field(
        check, "capability_scenario_report"
    )

    run_none = capability_scenario_verifier.run_capability_gates(CAP_ID, repo_root, None)
    assert field(run_none, "hit") == field(check, "hit")
    assert field(run_none, "capability_scenario_report") == field(
        check, "capability_scenario_report"
    )

    assert _calls(log_path) == []
    after = _snapshot(repo_root)
    assert after == before


def test_misses_give_hit_false_and_null_report(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)

    # No record
    record_path = repo_root / RECORD_REL
    assert not record_path.exists()
    res = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(res, "hit") is False
    assert field(res, "capability_scenario_report") is None

    record_path, record = _prime(repo_root)

    # Record that is not valid JSON
    record_path.write_text("{ this is not json")
    res = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(res, "hit") is False
    assert field(res, "capability_scenario_report") is None

    # Record with a different gate_version
    stale = dict(record)
    stale["gate_version"] = "capability_scenario_verifier@0.0.1-other"
    record_path.write_text(json.dumps(stale, indent=2))
    res = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(res, "hit") is False
    assert field(res, "capability_scenario_report") is None


def test_unknown_capability_raises_from_both(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.check_capability_provenance("P-NO-SUCH-THING", repo_root)

    with pytest.raises(capability_scenario_verifier.UnknownCapabilityError):
        capability_scenario_verifier.run_capability_gates("P-NO-SUCH-THING", repo_root, "m")