import provenance_tracker

import json
import textwrap
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_component(repo_root: Path, slug: str) -> None:
    upper = slug.upper()
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        textwrap.dedent(
            f"""\
            ---
            id: comp-{slug}
            title: {slug.capitalize()} component
            status: draft
            owners: [team-a]
            sealed: false
            realizes: []
            depends_on: []
            ---

            # comp-{slug}

            A small synthetic component used as a test fixture.
            """
        ),
    )
    _write(
        repo_root / "specs" / "components" / slug / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "acceptance" / f"AC-{upper}-001.md",
        textwrap.dedent(
            f"""\
            # AC-{upper}-001

            Covers: R-{upper}-001
            Kind: compiled

            ```gherkin
            Given the component
            When it is loaded
            Then it exists
            ```
            """
        ),
    )
    _write(repo_root / "gen" / slug / f"{slug}.py", "VALUE = 1\n")


def _install_fakes(repo_root: Path, log_path: Path, hits: dict, impacted: list) -> None:
    log_literal = repr(str(log_path))
    hits_literal = repr(hits)
    impacted_literal = repr(impacted)

    provenance_checker_src = textwrap.dedent(
        f"""\
        import json

        _LOG = {log_literal}
        _HITS = {hits_literal}


        def _log(name, component_id):
            with open(_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({{"fn": name, "component_id": component_id}}) + "\\n")


        class _ProvenanceKey(dict):
            # An object exposing both fields as attributes (also dict-readable).
            def __getattr__(self, name):
                try:
                    return self[name]
                except KeyError:
                    raise AttributeError(name)


        def current_sealed_key(component_id, repo_root):
            _log("current_sealed_key", component_id)
            return None


        def current_provenance_key(component_id, repo_root):
            _log("current_provenance_key", component_id)
            return _ProvenanceKey(
                spec_bundle_hash="sha256:" + "a" * 64,
                gate_versions={{
                    "compiler": "criterion-compiler@1.0.0",
                    "generated_test": "generated_test@1.0.0",
                    "verifier": "verifier-orchestrator@2.0.0",
                    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
                    "secret_scanner": "secret_scanner@0.0.0",
                }},
            )


        def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
            _log("check_provenance", component_id)
            if not _HITS.get(component_id, False):
                return {{
                    "hit": False,
                    "verification_report": None,
                    "license_scan": None,
                    "secret_scan": None,
                }}
            return {{
                "hit": True,
                "verification_report": {{
                    "component_id": component_id,
                    "criteria": [
                        {{"id": "AC-X-001", "covers": "R-X-001", "kind": "compiled", "result": "pass"}}
                    ],
                    "requirement_results": {{"R-X-001": "pass"}},
                    "interface_drift": False,
                    "mutation_score": 0.92,
                    "overall": "pass",
                }},
                "license_scan": {{
                    "component_id": component_id,
                    "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
                    "evaluated": True,
                    "reason": None,
                    "similarity_score": 0.1,
                    "block_threshold": 0.7,
                    "blocked": False,
                    "matches": [],
                    "notified": False,
                    "notification_delivery_error": None,
                    "cache_hit": False,
                }},
                "secret_scan": {{
                    "scope": "full",
                    "gate_version": "secret_scanner@0.0.0",
                    "flagged": False,
                    "matches": [],
                    "allowed": [],
                    "unused_allowlist_entries": [],
                    "notified": False,
                    "notification_delivery_error": None,
                    "cache_hit": False,
                }},
            }}


        def check_sealed_provenance(component_id, repo_root):
            _log("check_sealed_provenance", component_id)
            return {{
                "hit": False,
                "sealed": False,
                "reason": "not_sealed",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
                "owners": None,
                "source_hash": None,
                "written_at": None,
            }}
        """
    )

    impact_analyzer_src = textwrap.dedent(
        f"""\
        import json

        _LOG = {log_literal}
        _IMPACTED = {impacted_literal}


        def compute_blast_radius(changed_ids, repo_root):
            with open(_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({{"fn": "compute_blast_radius", "changed_ids": list(changed_ids)}}) + "\\n")
            return {{
                "impacted": [dict(entry) for entry in _IMPACTED],
                "precondition_error": None,
            }}
        """
    )

    capability_src = textwrap.dedent(
        f"""\
        import json

        _LOG = {log_literal}

        GATE_VERSION = "capability_scenario_verifier@2.0.0"


        class UnknownCapabilityError(ValueError):
            pass


        class ModelRequiredError(ValueError):
            pass


        def _log(name, capability_id):
            with open(_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({{"fn": name, "capability_id": capability_id}}) + "\\n")


        def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
            return {{}}


        def check_capability_provenance(capability_id, repo_root):
            _log("check_capability_provenance", capability_id)
            return {{
                "hit": True,
                "capability_scenario_report": {{capability_id: {{"overall": "pass", "scenarios": []}}}},
            }}


        def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
            _log("run_capability_gates", capability_id)
            return {{
                "hit": False,
                "capability_scenario_report": {{capability_id: {{"overall": "pass", "scenarios": []}}}},
            }}
        """
    )

    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", provenance_checker_src)
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_analyzer_src)
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        capability_src,
    )


def _read_log(log_path: Path) -> list:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _setup(tmp_path: Path, hits: dict, impacted: list):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** — a test fixture.\n")
    for entry in impacted:
        slug = entry["component_id"][len("comp-"):]
        _make_component(repo_root, slug)
    log_path = tmp_path / "invocations.log"
    _install_fakes(repo_root, log_path, hits, impacted)
    return repo_root, log_path


def test_dict_shaped_dependency_results_are_read_without_attribute_error(tmp_path):
    impacted = [
        {"component_id": "comp-foo", "reason": "direct", "via": None},
    ]
    repo_root, log_path = _setup(tmp_path, {"comp-foo": True}, impacted)

    try:
        report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-foo"])
    except AttributeError as exc:  # pragma: no cover - the failure being guarded against
        raise AssertionError(f"check_readiness raised AttributeError on dict-shaped results: {exc!r}")

    calls = _read_log(log_path)
    assert any(c["fn"] == "compute_blast_radius" for c in calls)
    assert any(c["fn"] == "check_provenance" and c["component_id"] == "comp-foo" for c in calls)

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert "comp-foo" in components
    entry = components["comp-foo"]
    assert field(entry, "hit") is True
    assert field(field(entry, "verification_report"), "overall") == "pass"
    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []


def test_dict_shaped_hit_and_component_id_distinguish_hit_from_miss(tmp_path):
    impacted = [
        {"component_id": "comp-foo", "reason": "direct", "via": None},
        {"component_id": "comp-bar", "reason": "transitive-interface", "via": "comp-foo"},
    ]
    repo_root, log_path = _setup(tmp_path, {"comp-foo": True, "comp-bar": False}, impacted)

    try:
        report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-foo"])
    except AttributeError as exc:  # pragma: no cover - the failure being guarded against
        raise AssertionError(f"check_readiness raised AttributeError on dict-shaped results: {exc!r}")

    calls = _read_log(log_path)
    checked = {c["component_id"] for c in calls if c["fn"] == "check_provenance"}
    assert {"comp-foo", "comp-bar"} <= checked

    components = field(report, "components")
    assert set(components) >= {"comp-foo", "comp-bar"}
    assert field(components["comp-foo"], "hit") is True
    assert field(components["comp-bar"], "hit") is False

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-bar" in r for r in reasons)