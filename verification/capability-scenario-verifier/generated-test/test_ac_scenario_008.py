import os

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_component(repo_root, slug, capability_id, code_filename=None, code_content="X = 1\n"):
    comp_dir = repo_root / "specs" / "components" / slug
    frontmatter = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug}\n"
        "status: draft\n"
        "owners: [eng]\n"
        f"realizes: [{capability_id}]\n"
        "sealed: false\n"
        "---\n"
    )
    _write(comp_dir / "component.md", frontmatter)
    gen_dir = repo_root / "gen" / slug
    gen_dir.mkdir(parents=True, exist_ok=True)
    fname = code_filename or f"{slug}_mod.py"
    (gen_dir / fname).write_text(code_content)
    return gen_dir


def _make_capability(repo_root, capability_id, scenario_id, kind,
                      given="Given a thing", when="When the thing runs", then="Then it passes"):
    name = capability_id.lower().replace("-", "_")
    content = (
        "---\n"
        f"id: {capability_id}\n"
        f"title: {capability_id}\n"
        "status: draft\n"
        "owners: [eng]\n"
        "---\n"
        "\n"
        f"### {scenario_id}\n"
        "\n"
        f"Covers: {capability_id}\n"
        f"Kind: {kind}\n"
        "\n"
        "```gherkin\n"
        f"{given}\n"
        f"{when}\n"
        f"{then}\n"
        "```\n"
    )
    _write(repo_root / "specs" / "product" / f"{name}.md", content)


def test_generated_test_failure_writes_file_and_fails(tmp_path):
    repo_root = tmp_path / "repo1"
    capability_id = "P-DEMO1"
    scenario_id = "CS-DEMO1-001"
    _make_component(repo_root, "foo1", capability_id)
    _make_capability(repo_root, capability_id, scenario_id, kind="generated-test")

    returned_path = "verification/capabilities/P-DEMO1/generated-test/test_cs_demo1_001.py"

    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": returned_path,
                "content": "def test_x():\n    assert False\n",
            },
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo1"], repo_root, test_author=fake_test_author
    )

    cap_report = _get(report, capability_id)
    assert _get(cap_report, "overall") == "fail"
    scenarios = _get(cap_report, "scenarios")
    matching = [s for s in scenarios if _get(s, "id") == scenario_id]
    assert len(matching) == 1
    assert _get(matching[0], "result") == "fail"

    written = repo_root / returned_path
    assert written.exists()
    assert written.read_text() == "def test_x():\n    assert False\n"


def test_escaping_paths_fail_and_nothing_written(tmp_path):
    other_dir = tmp_path / "separate_escape_target"
    other_dir.mkdir()
    abs_escape_path = str(other_dir / "escape.py")

    cases = [
        ("esc0", "P-ESC0", "CS-ESC0-001", "../escape.py"),
        ("esc1", "P-ESC1", "CS-ESC1-001", abs_escape_path),
        ("esc2", "P-ESC2", "CS-ESC2-001", "notverification/x.py"),
    ]

    for slug, capability_id, scenario_id, bad_path in cases:
        repo_root = tmp_path / f"repo_{slug}"
        _make_component(repo_root, slug, capability_id)
        _make_capability(repo_root, capability_id, scenario_id, kind="generated-test")

        def fake_test_author(bundle, _bad_path=bad_path):
            return {
                "model_call_error": None,
                "file": {"path": _bad_path, "content": "def test_x():\n    assert True\n"},
            }

        report = capability_scenario_verifier.run_capability_scenarios(
            [f"comp-{slug}"], repo_root, test_author=fake_test_author
        )

        cap_report = _get(report, capability_id)
        scenarios = _get(cap_report, "scenarios")
        matching = [s for s in scenarios if _get(s, "id") == scenario_id]
        assert len(matching) == 1
        assert _get(matching[0], "result") == "fail"

        if os.path.isabs(bad_path):
            assert not os.path.exists(bad_path)
        else:
            assert not (repo_root / bad_path).exists()
            assert not os.path.exists(os.path.realpath(str(repo_root / bad_path)))


def test_model_call_error_or_missing_file_is_fail(tmp_path):
    cases = [
        ("err0", "P-ERR0", "CS-ERR0-001", {"model_call_error": {"message": "boom"}, "file": None}),
        ("err1", "P-ERR1", "CS-ERR1-001", {"model_call_error": None, "file": None}),
        ("err2", "P-ERR2", "CS-ERR2-001", {"model_call_error": None}),
    ]

    for slug, capability_id, scenario_id, outcome in cases:
        repo_root = tmp_path / f"repo_{slug}"
        _make_component(repo_root, slug, capability_id)
        _make_capability(repo_root, capability_id, scenario_id, kind="generated-test")

        def fake_test_author(bundle, _outcome=outcome):
            return _outcome

        report = capability_scenario_verifier.run_capability_scenarios(
            [f"comp-{slug}"], repo_root, test_author=fake_test_author
        )

        cap_report = _get(report, capability_id)
        scenarios = _get(cap_report, "scenarios")
        matching = [s for s in scenarios if _get(s, "id") == scenario_id]
        assert len(matching) == 1
        assert _get(matching[0], "result") == "fail"


def test_pass_runs_with_component_code_on_pythonpath(tmp_path):
    repo_root = tmp_path / "repo_pass"
    capability_id = "P-PASS"
    scenario_id = "CS-PASS-001"
    gen_dir = _make_component(
        repo_root, "foo4", capability_id,
        code_filename="foo_mod.py",
        code_content="def value():\n    return 7\n",
    )
    assert (gen_dir / "foo_mod.py").exists()

    _make_capability(repo_root, capability_id, scenario_id, kind="generated-test")

    returned_path = "verification/capabilities/P-PASS/generated-test/test_cs_pass_001.py"
    test_content = (
        "import foo_mod\n\n\n"
        "def test_value():\n"
        "    assert foo_mod.value() == 7\n"
    )

    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {"path": returned_path, "content": test_content},
        }

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo4"], repo_root, test_author=fake_test_author
    )

    cap_report = _get(report, capability_id)
    assert _get(cap_report, "overall") == "pass"
    scenarios = _get(cap_report, "scenarios")
    matching = [s for s in scenarios if _get(s, "id") == scenario_id]
    assert len(matching) == 1
    assert _get(matching[0], "result") == "pass"