import json
import textwrap


def _write_module(repo_root, dep_slug, module_name, source):
    mod_dir = repo_root / "gen" / dep_slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(source, encoding="utf-8")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _build_fixture(repo_root, log_path):
    log_literal = repr(str(log_path))

    spec_linter_src = textwrap.dedent(f"""
        import json

        LOG_PATH = {log_literal}

        def _log(record):
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\\n")

        def lint(paths, repo_root, strict=False, judge=None):
            _log({{"dep": "spec-linter", "fn": "lint"}})
            return {{"findings": [], "summary": {{"hard_failures": 0, "warnings": 0, "skipped": 0}}}}
    """)
    _write_module(repo_root, "spec-linter", "spec_linter", spec_linter_src)

    impact_analyzer_src = textwrap.dedent(f"""
        import json

        LOG_PATH = {log_literal}

        def _log(record):
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\\n")

        def compute_blast_radius(changed_ids, repo_root):
            _log({{"dep": "impact-analyzer", "fn": "compute_blast_radius"}})
            return {{
                "impacted": [{{"component_id": "comp-foo", "reason": "direct", "via": None}}],
                "precondition_error": None,
            }}
    """)
    _write_module(repo_root, "impact-analyzer", "impact_analyzer", impact_analyzer_src)

    spec_bundle_assembler_src = textwrap.dedent(f"""
        import json

        LOG_PATH = {log_literal}

        def _log(record):
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\\n")

        def assemble(component_id, repo_root=None, mode="cold"):
            _log({{"dep": "spec-bundle-assembler", "fn": "assemble", "component_id": component_id, "mode": mode}})
            return {{
                "component_id": component_id,
                "spec_bundle_hash": "sha256:fake",
                "spec": "spec text",
                "interface": "interface text",
                "constraints": "constraints text",
                "dependency_interfaces": {{}},
                "dependency_context": {{}},
                "dependency_usage": {{}},
                "vars": {{}},
                "glossary": "glossary text",
                "hint_code": {{"fake.py": "fake content"}} if mode == "hint" else None,
            }}
    """)
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", spec_bundle_assembler_src)

    generator_src = textwrap.dedent(f"""
        import json

        LOG_PATH = {log_literal}

        def _log(record):
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\\n")

        def _cid(bundle):
            if isinstance(bundle, dict):
                return bundle.get("component_id")
            return getattr(bundle, "component_id", None)

        def _hash(bundle):
            if isinstance(bundle, dict):
                return bundle.get("spec_bundle_hash")
            return getattr(bundle, "spec_bundle_hash", None)

        def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
            cid = _cid(bundle)
            _log({{"dep": "generator", "fn": "generate", "component_id": cid, "model": model}})
            return {{
                "component_id": cid,
                "spec_bundle_hash": _hash(bundle),
                "model": model,
                "prompt_version": "v1",
                "cache_hit": False,
                "files": {{"fake.py": "fake generated content"}},
                "model_call_error": None,
                "refused": None,
                "retry_feedback": retry_feedback,
            }}
    """)
    _write_module(repo_root, "generator", "generator", generator_src)

    llm_endpoint_src = textwrap.dedent(f"""
        import json

        LOG_PATH = {log_literal}

        def _log(record):
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\\n")

        def complete(prompt, model, *, backend=None, **params):
            _log({{"dep": "llm-endpoint", "fn": "complete", "model": model}})
            return {{
                "text": json.dumps({{
                    "completeness_score": 0.9,
                    "completeness_rationale": "fake rationale",
                    "redundancy_flags": [],
                }}),
                "model": model,
                "backend": backend or "fake-backend",
                "model_call_error": None,
            }}
    """)
    _write_module(repo_root, "llm-endpoint", "llm_endpoint", llm_endpoint_src)


def test_ac_assist_003(tmp_path):
    import spec_completeness_assistant as target

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = repo_root / "calls.log"

    _build_fixture(repo_root, log_path)

    changed_ids = ["comp-foo"]

    # --- Scenario 1: model configured ---
    report = target.assist(changed_ids, repo_root, model="fake-model")

    hint_previews = _get(report, "hint_previews")
    assert set(hint_previews.keys()) == {"comp-foo"}

    log_entries = _read_log(log_path)

    assemble_calls = [
        e for e in log_entries if e.get("dep") == "spec-bundle-assembler" and e.get("fn") == "assemble"
    ]
    assert len(assemble_calls) == 1
    assert assemble_calls[0]["component_id"] == "comp-foo"
    assert assemble_calls[0]["mode"] == "hint"
    assert all(e["mode"] != "cold" for e in assemble_calls)

    generate_calls = [e for e in log_entries if e.get("dep") == "generator" and e.get("fn") == "generate"]
    assert len(generate_calls) == 1
    assert generate_calls[0]["component_id"] == "comp-foo"

    # Reset the log for the second scenario.
    log_path.write_text("", encoding="utf-8")

    # --- Scenario 2: no model configured ---
    report_no_model = target.assist(changed_ids, repo_root)

    hint_previews_no_model = _get(report_no_model, "hint_previews")
    assert set(hint_previews_no_model.keys()) == {"comp-foo"}

    log_entries_no_model = _read_log(log_path)

    assemble_calls_no_model = [
        e for e in log_entries_no_model if e.get("dep") == "spec-bundle-assembler" and e.get("fn") == "assemble"
    ]
    assert len(assemble_calls_no_model) == 1
    assert assemble_calls_no_model[0]["mode"] == "hint"

    generate_calls_no_model = [
        e for e in log_entries_no_model if e.get("dep") == "generator" and e.get("fn") == "generate"
    ]
    assert generate_calls_no_model == []