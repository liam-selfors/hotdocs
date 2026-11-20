# hotdocs-criterion: sha256:d780daaceff4d1d86553ac95e9bf82f091447ca397da7f749f00480e127bd6cc
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST work.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )


def _write_fakes(repo_root, log_path, hit):
    if hit:
        result_src = (
            "    return {\n"
            "        'hit': True,\n"
            "        'reason': None,\n"
            "        'verification_report': {\n"
            "            'component_id': component_id,\n"
            "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'generated-test', 'result': 'pass'}],\n"
            "            'requirement_results': {'R-FOO-001': 'pass'},\n"
            "            'interface_drift': False,\n"
            "            'mutation_score': 0.9,\n"
            "            'mutation_error': None,\n"
            "            'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
            "                        'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
            "                        'lockfile_sha256': None}],\n"
            "            'overall': 'pass',\n"
            "        },\n"
            "        'license_scan': {\n"
            "            'component_id': component_id,\n"
            "            'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',\n"
            "            'evaluated': True,\n"
            "            'reason': None,\n"
            "            'similarity_score': 0.1,\n"
            "            'block_threshold': 0.7,\n"
            "            'blocked': False,\n"
            "            'matches': [],\n"
            "            'notified': False,\n"
            "            'notification_delivery_error': None,\n"
            "            'cache_hit': False,\n"
            "        },\n"
            "        'secret_scan': {\n"
            "            'scope': 'full',\n"
            "            'gate_version': 'secret_scanner@3.1.0',\n"
            "            'flagged': False,\n"
            "            'matches': [],\n"
            "            'allowed': [],\n"
            "            'unused_allowlist_entries': [],\n"
            "            'notified': False,\n"
            "            'notification_delivery_error': None,\n"
            "            'cache_hit': False,\n"
            "        },\n"
            "    }\n"
        )
    else:
        result_src = (
            "    return {\n"
            "        'hit': False,\n"
            "        'reason': 'no manifest',\n"
            "        'verification_report': None,\n"
            "        'license_scan': None,\n"
            "        'secret_scan': None,\n"
            "    }\n"
        )

    checker_src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "class _Key:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "    def __getitem__(self, name):\n"
        "        return getattr(self, name)\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key ' + str(component_id))\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key ' + str(component_id))\n"
        "    return _Key(\n"
        "        'sha256:abc123',\n"
        "        {\n"
        "            'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@2.0.0',\n"
        "            'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "            'generator': 'generator@3.0.0+v11',\n"
        "        },\n"
        "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "          'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
        "          'lockfile_sha256': None}],\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance ' + str(component_id))\n"
        + result_src
        + "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance ' + str(component_id))\n"
        "    return {\n"
        "        'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "        'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "        'owners': None, 'source_hash': None, 'written_at': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", checker_src)

    impact_src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('compute_blast_radius ' + ','.join(changed_ids) + '\\n')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_src)

    csv_src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log('run_capability_scenarios')\n"
        "    return {}\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance ' + str(capability_id))\n"
        "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates ' + str(capability_id))\n"
        "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        csv_src,
    )


def _run(repo_root):
    try:
        return provenance_tracker.check_readiness(repo_root, changed_ids=["comp-foo"])
    except AttributeError as exc:  # pragma: no cover - the failure this criterion guards
        pytest.fail("check_readiness raised AttributeError on dict-shaped results: " + repr(exc))


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def test_dict_shaped_hit_is_read_correctly(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fixture(repo_root)
    _write_fakes(repo_root, log_path, hit=True)

    report = _run(repo_root)

    lines = _log_lines(log_path)
    assert any(line.startswith("compute_blast_radius") for line in lines), lines
    assert "check_provenance comp-foo" in lines, lines

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert "comp-foo" in components
    entry = components["comp-foo"]
    assert field(entry, "hit") is True
    assert field(field(entry, "verification_report"), "overall") == "pass"
    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []


def test_dict_shaped_miss_is_read_correctly(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fixture(repo_root)
    _write_fakes(repo_root, log_path, hit=False)

    report = _run(repo_root)

    lines = _log_lines(log_path)
    assert any(line.startswith("compute_blast_radius") for line in lines), lines
    assert "check_provenance comp-foo" in lines, lines

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert "comp-foo" in components
    assert field(components["comp-foo"], "hit") is False
    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-foo" in str(r) for r in reasons), reasons
    json.dumps(reasons)