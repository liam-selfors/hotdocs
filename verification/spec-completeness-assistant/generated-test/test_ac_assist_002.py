import os

import spec_completeness_assistant


def _write_module(repo_root, slug, module_name, source):
    mod_dir = os.path.join(repo_root, "gen", slug)
    os.makedirs(mod_dir, exist_ok=True)
    with open(os.path.join(mod_dir, module_name + ".py"), "w") as f:
        f.write(source)


def _read_dual(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def test_predicted_blast_radius_lists_exactly_comp_alpha_and_comp_beta(tmp_path):
    repo_root = str(tmp_path)
    log_path = str(tmp_path / "_invocations.log")

    spec_linter_src = (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    with open(%r, 'a') as f:\n"
        "        f.write('lint\\n')\n"
        "    return {\n"
        "        'findings': [],\n"
        "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},\n"
        "    }\n"
    ) % log_path

    impact_analyzer_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(%r, 'a') as f:\n"
        "        f.write('compute_blast_radius\\n')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-alpha', 'reason': 'direct', 'via': None},\n"
        "            {'component_id': 'comp-beta', 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    ) % log_path

    spec_bundle_assembler_src = (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    with open(%r, 'a') as f:\n"
        "        f.write('assemble:' + component_id + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:fake',\n"
        "        'spec': '',\n"
        "        'interface': '',\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': {},\n"
        "    }\n"
    ) % log_path

    generator_src = (
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    with open(%r, 'a') as f:\n"
        "        f.write('generate\\n')\n"
        "    bundle_component_id = (\n"
        "        bundle.get('component_id')\n"
        "        if isinstance(bundle, dict)\n"
        "        else getattr(bundle, 'component_id', None)\n"
        "    )\n"
        "    return {\n"
        "        'component_id': bundle_component_id,\n"
        "        'spec_bundle_hash': 'sha256:fake',\n"
        "        'model': model,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'files': {'fake.py': '# fake'},\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "    }\n"
    ) % log_path

    _write_module(repo_root, "spec-linter", "spec_linter", spec_linter_src)
    _write_module(repo_root, "impact-analyzer", "impact_analyzer", impact_analyzer_src)
    _write_module(
        repo_root,
        "spec-bundle-assembler",
        "spec_bundle_assembler",
        spec_bundle_assembler_src,
    )
    _write_module(repo_root, "generator", "generator", generator_src)

    report = spec_completeness_assistant.assist(["R-DRAFT-001"], repo_root)

    predicted_blast_radius = _read_dual(report, "predicted_blast_radius")
    assert sorted(predicted_blast_radius) == ["comp-alpha", "comp-beta"]

    with open(log_path) as f:
        log_contents = f.read()

    assert "lint" in log_contents
    assert "compute_blast_radius" in log_contents
    assert "assemble:comp-alpha" in log_contents
    assert "assemble:comp-beta" in log_contents