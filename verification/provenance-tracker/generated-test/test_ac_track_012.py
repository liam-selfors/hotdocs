import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_fixture_component(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)

    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo Component\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "sealed: true\n"
        "source_path: vendor/foo/foo.py\n"
        "---\n\n"
        "# comp-foo\n"
    )

    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n"
        "**R-FOO-001** -- Foo does something.\n"
    )

    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n\n"
        "Foo behaves correctly.\n"
    )


def _write_fake_provenance_checker(repo_root, log_path):
    mod_dir = repo_root / "gen" / "provenance-checker"
    mod_dir.mkdir(parents=True, exist_ok=True)
    source = f'''
class _ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return _ProvenanceKey(
        "sha256:" + "a" * 64,
        {{
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@1.0.0",
            "license_scanner": "license_scanner@1.0.0",
            "secret_scanner": "secret_scanner@1.0.0",
        }},
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    with open({str(log_path)!r}, "a") as f:
        f.write(component_id + "\\n")
    return {{
        "hit": True,
        "verification_report": {{
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {{}},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        }},
        "license_scan": {{
            "component_id": component_id,
            "gate_version": "license_scanner@1.0.0",
            "similarity_score": 0.0,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }},
        "secret_scan": {{
            "scope": "full",
            "gate_version": "secret_scanner@1.0.0",
            "flagged": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }},
    }}
'''
    (mod_dir / "provenance_checker.py").write_text(source)


def _write_fake_impact_analyzer(repo_root, log_path):
    mod_dir = repo_root / "gen" / "impact-analyzer"
    mod_dir.mkdir(parents=True, exist_ok=True)
    source = f'''
def compute_blast_radius(changed_ids, repo_root):
    with open({str(log_path)!r}, "a") as f:
        f.write(",".join(changed_ids) + "\\n")
    return {{
        "impacted": [
            {{
                "component_id": "comp-foo",
                "reason": "direct",
                "via": None,
            }}
        ],
        "precondition_error": None,
    }}
'''
    (mod_dir / "impact_analyzer.py").write_text(source)


def test_check_readiness_reads_dict_shaped_dependency_results(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_fixture_component(repo_root)

    pc_log = tmp_path / "pc_invocations.log"
    ia_log = tmp_path / "ia_invocations.log"

    _write_fake_provenance_checker(repo_root, pc_log)
    _write_fake_impact_analyzer(repo_root, ia_log)

    report = provenance_tracker.check_readiness(
        repo_root=repo_root,
        changed_ids=["comp-foo"],
        model=None,
        seed=0,
        llm_backend=None,
    )

    assert _get(report, "scope") == "blast-radius"

    components = _get(report, "components")
    assert "comp-foo" in components
    foo_result = components["comp-foo"]
    assert _get(foo_result, "hit") is True

    assert _get(report, "ready") is True
    assert _get(report, "not_ready_reasons") == []

    assert ia_log.exists()
    assert ia_log.read_text().strip() == "comp-foo"

    assert pc_log.exists()
    assert pc_log.read_text().strip() == "comp-foo"