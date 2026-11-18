# hotdocs-criterion: sha256:809a54635f6462b3bc8bdf4e6571e23aa08547a2b75700642c283d6c8693f3ab
"""AC-TRACK-012: check_readiness reads dict-shaped dependency results.

Covers: R-TRACK-012
"""

import json
from pathlib import Path

import pytest

import provenance_tracker


SPEC_HASH = "sha256:" + "ab" * 32
GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST do foo.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo happens\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


def _write_fake_provenance_checker(repo_root, log_path, hit):
    if hit:
        result_src = (
            "    return {\n"
            "        'hit': True,\n"
            "        'verification_report': {\n"
            "            'component_id': component_id,\n"
            "            'criteria': [\n"
            "                {'id': 'AC-FOO-001', 'covers': 'R-FOO-001',\n"
            "                 'kind': 'generated-test', 'result': 'pass'},\n"
            "            ],\n"
            "            'requirement_results': {'R-FOO-001': 'pass'},\n"
            "            'interface_drift': False,\n"
            "            'mutation_score': 0.9,\n"
            "            'mutation_error': None,\n"
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
            "            'gate_version': 'secret_scanner@0.0.0',\n"
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
            "        'verification_report': None,\n"
            "        'license_scan': None,\n"
            "        'secret_scan': None,\n"
            "    }\n"
        )
    src = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
        "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        "\n"
        "\n"
        "class _Key(dict):\n"
        "    def __getattr__(self, name):\n"
        "        try:\n"
        "            return self[name]\n"
        "        except KeyError:\n"
        "            raise AttributeError(name)\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log(['current_sealed_key', component_id])\n"
        "    return None\n"
        "\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log(['current_provenance_key', component_id])\n"
        "    return _Key(spec_bundle_hash=SPEC_HASH, gate_versions=dict(GATE_VERSIONS))\n"
        "\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log(['check_provenance', component_id, spec_bundle_hash])\n"
        + result_src
        + "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log(['check_sealed_provenance', component_id])\n"
        "    return {\n"
        "        'hit': False,\n"
        "        'sealed': False,\n"
        "        'reason': 'not_sealed',\n"
        "        'verification_report': None,\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "        'owners': None,\n"
        "        'source_hash': None,\n"
        "        'written_at': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", src)


def _write_fake_impact_analyzer(repo_root, log_path):
    src = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(['compute_blast_radius', list(changed_ids)]) + '\\n')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", src)


def _write_fake_capability_verifier(repo_root, log_path):
    src = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'capability_scenario_verifier@2.0.0'\n"
        "\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "\n"
        "def _report(capability_id):\n"
        "    return {capability_id: {'overall': 'pass', 'scenarios': []}}\n"
        "\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log(['run_capability_scenarios', list(blast_radius)])\n"
        "    return {}\n"
        "\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log(['check_capability_provenance', capability_id])\n"
        "    return {'hit': True, 'capability_scenario_report': _report(capability_id)}\n"
        "\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log(['run_capability_gates', capability_id])\n"
        "    return {'hit': True, 'capability_scenario_report': _report(capability_id)}\n"
    )
    _write(
        repo_root
        / "gen"
        / "capability-scenario-verifier"
        / "capability_scenario_verifier.py",
        src,
    )


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize("hit", [True, False])
def test_check_readiness_reads_dict_shaped_dependency_results(tmp_path, hit):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    _build_corpus(repo_root)
    _write_fake_provenance_checker(repo_root, log_path, hit)
    _write_fake_impact_analyzer(repo_root, log_path)
    _write_fake_capability_verifier(repo_root, log_path)

    try:
        report = provenance_tracker.check_readiness(
            Path(repo_root), changed_ids=["comp-foo"]
        )
    except AttributeError as exc:  # pragma: no cover - the failure being guarded
        pytest.fail(
            "check_readiness raised AttributeError on dict-shaped dependency "
            "results: " + repr(exc)
        )

    calls = _read_log(log_path)

    # The fake impact-analyzer was consulted and its dict entry's
    # component_id was read correctly, driving the provenance check.
    assert ["compute_blast_radius", ["comp-foo"]] in calls
    prov_calls = [c for c in calls if c[0] == "check_provenance"]
    assert prov_calls, "check_provenance was never called: " + repr(calls)
    assert all(c[1] == "comp-foo" for c in prov_calls)
    assert prov_calls[0][2] == SPEC_HASH

    assert field(report, "scope") == "blast-radius"

    components = field(report, "components")
    assert "comp-foo" in components
    entry = components["comp-foo"]
    assert field(entry, "hit") is hit

    ready = field(report, "ready")
    reasons = list(field(report, "not_ready_reasons"))
    if hit:
        assert ready is True, "expected ready; reasons: " + repr(reasons)
        assert not any("comp-foo" in str(r) for r in reasons)
    else:
        assert ready is False
        assert any("comp-foo" in str(r) for r in reasons), repr(reasons)