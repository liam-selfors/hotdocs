import json
import tempfile
from pathlib import Path

import provenance_tracker


def _get(obj, key):
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)


def _read_jsonl(path):
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _component_md(slug, comp_id):
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {slug}\n"
        "status: draft\n"
        "owners: [tester]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}.py\n"
        "---\n"
        "\n"
        f"# {slug}\n"
        "\n"
        "Fixture component for AC-TRACK-011 isolation testing.\n"
    )


def _requirement_md(req_id):
    return (
        f"# {req_id}\n"
        "\n"
        "Fixture requirement for AC-TRACK-011 isolation testing.\n"
    )


def _acceptance_md(ac_id, req_id):
    return (
        f"# {ac_id}\n"
        "\n"
        f"Covers: {req_id}\n"
        "Kind: llm-judge\n"
        "\n"
        "Fixture acceptance criterion satisfying Covers linkage for lint cleanliness.\n"
    )


def _build_component_fixture(repo_root, comp_id):
    slug = comp_id[len("comp-"):]
    base = repo_root / "specs" / "components" / slug
    base.mkdir(parents=True, exist_ok=True)
    (base / "component.md").write_text(_component_md(slug, comp_id), encoding="utf-8")

    req_name = slug.upper().replace("-", "")
    req_id = f"R-{req_name}-001"
    ac_id = f"AC-{req_name}-001"

    (base / "requirements").mkdir(parents=True, exist_ok=True)
    (base / "requirements" / f"{req_id}.md").write_text(_requirement_md(req_id), encoding="utf-8")

    (base / "acceptance").mkdir(parents=True, exist_ok=True)
    (base / "acceptance" / f"{ac_id}.md").write_text(_acceptance_md(ac_id, req_id), encoding="utf-8")


def _impact_analyzer_source(impacted_ids):
    impacted = [{"component_id": cid, "reason": "direct", "via": None} for cid in impacted_ids]
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    log_path = Path(repo_root) / '_fake_impact_analyzer_calls.jsonl'\n"
        "    with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'changed_ids': list(changed_ids)}) + '\\n')\n"
        "    return {'impacted': " + repr(impacted) + ", 'precondition_error': None}\n"
    )


def _provenance_checker_source():
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    log_path = Path(repo_root) / '_fake_provenance_checker_calls.jsonl'\n"
        "    with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'component_id': component_id}) + '\\n')\n"
        "    return {\n"
        "        'hit': False,\n"
        "        'verification_report': None,\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "    }\n"
    )


def _capability_scenario_verifier_source():
    return (
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    return {}\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    return {'hit': False, 'capability_scenario_report': None}\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, judge=None, test_author=None):\n"
        "    return {'hit': False, 'capability_scenario_report': None}\n"
    )


def _build_repo(repo_root, impacted_ids):
    gen_dir = repo_root / "gen"

    impact_dir = gen_dir / "impact-analyzer"
    impact_dir.mkdir(parents=True, exist_ok=True)
    (impact_dir / "impact_analyzer.py").write_text(
        _impact_analyzer_source(impacted_ids), encoding="utf-8"
    )

    prov_dir = gen_dir / "provenance-checker"
    prov_dir.mkdir(parents=True, exist_ok=True)
    (prov_dir / "provenance_checker.py").write_text(
        _provenance_checker_source(), encoding="utf-8"
    )

    cap_dir = gen_dir / "capability-scenario-verifier"
    cap_dir.mkdir(parents=True, exist_ok=True)
    (cap_dir / "capability_scenario_verifier.py").write_text(
        _capability_scenario_verifier_source(), encoding="utf-8"
    )

    for comp_id in impacted_ids:
        _build_component_fixture(repo_root, comp_id)


def test_ac_track_011_check_readiness_isolates_repo_root_dependencies():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        repo_a = Path(tmp_a)
        repo_b = Path(tmp_b)
        ids_a = ["comp-alpha-one", "comp-alpha-two"]
        ids_b = ["comp-beta-one", "comp-beta-two"]
        _build_repo(repo_a, ids_a)
        _build_repo(repo_b, ids_b)

        result_a = provenance_tracker.check_readiness(
            repo_root=repo_a, changed_ids=["R-FAKE-CHANGE-A"], model=None, seed=0, llm_backend=None,
        )
        components_a = _get(result_a, "components")
        assert set(components_a.keys()) == set(ids_a)
        assert _get(result_a, "scope") == "blast-radius"

        result_b = provenance_tracker.check_readiness(
            repo_root=repo_b, changed_ids=["R-FAKE-CHANGE-B"], model=None, seed=0, llm_backend=None,
        )
        components_b = _get(result_b, "components")
        assert set(components_b.keys()) == set(ids_b)
        assert _get(result_b, "scope") == "blast-radius"

        assert set(components_a.keys()) == set(ids_a)
        assert set(components_a.keys()).isdisjoint(set(ids_b))
        assert set(components_b.keys()).isdisjoint(set(ids_a))

        pc_log_a = _read_jsonl(repo_a / "_fake_provenance_checker_calls.jsonl")
        pc_log_b = _read_jsonl(repo_b / "_fake_provenance_checker_calls.jsonl")
        assert {entry["component_id"] for entry in pc_log_a} == set(ids_a)
        assert {entry["component_id"] for entry in pc_log_b} == set(ids_b)
        assert len(pc_log_a) == len(ids_a)
        assert len(pc_log_b) == len(ids_b)

        ia_log_a = _read_jsonl(repo_a / "_fake_impact_analyzer_calls.jsonl")
        ia_log_b = _read_jsonl(repo_b / "_fake_impact_analyzer_calls.jsonl")
        assert len(ia_log_a) == 1
        assert len(ia_log_b) == 1


def test_ac_track_011_check_readiness_isolates_repo_root_dependencies_reversed_order():
    with tempfile.TemporaryDirectory() as tmp_c, tempfile.TemporaryDirectory() as tmp_d:
        repo_c = Path(tmp_c)
        repo_d = Path(tmp_d)
        ids_c = ["comp-gamma-one", "comp-gamma-two"]
        ids_d = ["comp-delta-one", "comp-delta-two"]
        _build_repo(repo_c, ids_c)
        _build_repo(repo_d, ids_d)

        result_d = provenance_tracker.check_readiness(
            repo_root=repo_d, changed_ids=["R-FAKE-CHANGE-D"], model=None, seed=0, llm_backend=None,
        )
        components_d = _get(result_d, "components")
        assert set(components_d.keys()) == set(ids_d)

        result_c = provenance_tracker.check_readiness(
            repo_root=repo_c, changed_ids=["R-FAKE-CHANGE-C"], model=None, seed=0, llm_backend=None,
        )
        components_c = _get(result_c, "components")
        assert set(components_c.keys()) == set(ids_c)

        assert set(components_d.keys()).isdisjoint(set(ids_c))
        assert set(components_c.keys()).isdisjoint(set(ids_d))

        pc_log_c = _read_jsonl(repo_c / "_fake_provenance_checker_calls.jsonl")
        pc_log_d = _read_jsonl(repo_d / "_fake_provenance_checker_calls.jsonl")
        assert {entry["component_id"] for entry in pc_log_c} == set(ids_c)
        assert {entry["component_id"] for entry in pc_log_d} == set(ids_d)