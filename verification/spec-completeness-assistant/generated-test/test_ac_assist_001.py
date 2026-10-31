import spec_completeness_assistant as target


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _finding_matches(actual, expected):
    return all(_get(actual, key) == value for key, value in expected.items())


def _write_fake_module(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    module_dir = repo_root / "gen" / slug
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / f"{module_name}.py").write_text(source)


def _summary_for(findings):
    return {
        "hard_failures": sum(1 for f in findings if f["severity"] == "fail"),
        "warnings": sum(1 for f in findings if f["severity"] == "warn"),
        "skipped": sum(1 for f in findings if f["severity"] == "skipped"),
    }


def _setup_repo(tmp_path, log_path, lint_findings):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    summary = _summary_for(lint_findings)
    log_path_repr = repr(str(log_path))

    linter_src = (
        f"LOG_PATH = {log_path_repr}\n"
        f"FINDINGS = {lint_findings!r}\n"
        f"SUMMARY = {summary!r}\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write('spec-linter\\n')\n"
        "    return {'findings': FINDINGS, 'summary': SUMMARY}\n"
    )
    _write_fake_module(repo_root, "spec-linter", linter_src)

    impact_src = (
        f"LOG_PATH = {log_path_repr}\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write('impact-analyzer\\n')\n"
        "    return {'impacted': [], 'precondition_error': None}\n"
    )
    _write_fake_module(repo_root, "impact-analyzer", impact_src)

    assembler_src = (
        f"LOG_PATH = {log_path_repr}\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write('spec-bundle-assembler\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:deadbeef',\n"
        "        'spec': '',\n"
        "        'interface': '',\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': {} if mode == 'hint' else None,\n"
        "    }\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write('spec-bundle-assembler:criterion\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': '',\n"
        "        'criterion_text': '',\n"
        "        'requirement_text': '',\n"
        "        'interface': '',\n"
        "        'glossary': '',\n"
        "    }\n"
    )
    _write_fake_module(repo_root, "spec-bundle-assembler", assembler_src)

    generator_src = (
        f"LOG_PATH = {log_path_repr}\n"
        "\n"
        "def _get(obj, key, default=None):\n"
        "    if isinstance(obj, dict):\n"
        "        return obj.get(key, default)\n"
        "    return getattr(obj, key, default)\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write('generator\\n')\n"
        "    component_id = _get(bundle, 'component_id')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:deadbeef',\n"
        "        'model': model,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'files': {'x.py': 'pass\\n'},\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "    }\n"
    )
    _write_fake_module(repo_root, "generator", generator_src)

    endpoint_src = (
        "import json as _json\n"
        "\n"
        f"LOG_PATH = {log_path_repr}\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write('llm-endpoint\\n')\n"
        "    return {\n"
        "        'text': _json.dumps({'score': 0.9, 'rationale': 'ok', 'flags': []}),\n"
        "        'model': model,\n"
        "        'backend': 'fake-backend',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write_fake_module(repo_root, "llm-endpoint", endpoint_src)

    return repo_root


def test_assist_stops_after_fail_severity_lint_finding(tmp_path):
    log_path = tmp_path / "calls.log"
    fail_finding = {
        "rule_id": "R-LINT-003",
        "severity": "fail",
        "file": "specs/components/foo/component.md",
        "line": 12,
        "message": "depends_on references 'comp-bar', which does not exist",
    }
    repo_root = _setup_repo(tmp_path, log_path, [fail_finding])

    report = target.assist(["comp-foo"], repo_root, model="fake-model")

    lint_findings = _get(report, "lint_findings")
    assert len(lint_findings) == 1
    assert _finding_matches(lint_findings[0], fail_finding)
    assert _get(report, "predicted_blast_radius") == []
    assert _get(report, "hint_previews") == {}
    assert _get(report, "completeness_score") is None
    assert _get(report, "completeness_rationale") is None
    assert _get(report, "redundancy_flags") == []

    calls = log_path.read_text().splitlines() if log_path.exists() else []
    assert "impact-analyzer" not in calls
    assert "generator" not in calls
    assert "llm-endpoint" not in calls
    assert "spec-bundle-assembler" not in calls
    assert "spec-bundle-assembler:criterion" not in calls


def test_assist_proceeds_past_linting_on_warn_only_finding(tmp_path):
    log_path = tmp_path / "calls.log"
    warn_finding = {
        "rule_id": "R-LINT-010",
        "severity": "warn",
        "file": "specs/components/foo/component.md",
        "line": 5,
        "message": "a non-fatal lint concern",
    }
    repo_root = _setup_repo(tmp_path, log_path, [warn_finding])

    try:
        target.assist(["comp-foo"], repo_root, model="fake-model")
    except Exception:
        pass

    calls = log_path.read_text().splitlines() if log_path.exists() else []
    assert "impact-analyzer" in calls