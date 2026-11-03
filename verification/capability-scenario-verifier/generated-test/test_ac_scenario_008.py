import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


CAPABILITY_ID = "P-X"
SCENARIO_ID = "CS-X-001"
COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"


def _write_fixture_repo(repo_root, code_files=None):
    components_dir = repo_root / "specs" / "components" / COMPONENT_SLUG
    components_dir.mkdir(parents=True, exist_ok=True)
    (components_dir / "component.md").write_text(
        "---\n"
        f"id: {COMPONENT_ID}\n"
        "title: Foo Component\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        f"realizes: [{CAPABILITY_ID}]\n"
        "sealed: false\n"
        "---\n\n"
        "# Foo Component\n\n"
        "A fixture component used by AC-SCENARIO-008's tests.\n",
        encoding="utf-8",
    )

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    (product_dir / "foo.md").write_text(
        "---\n"
        f"id: {CAPABILITY_ID}\n"
        "title: Foo Capability\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "---\n\n"
        "# Foo Capability\n\n"
        f"### {SCENARIO_ID}\n\n"
        f"Covers: {CAPABILITY_ID}\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
        encoding="utf-8",
    )

    gen_dir = repo_root / "gen" / COMPONENT_SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    for rel_path, content in (code_files or {}).items():
        target = gen_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _make_test_author(outcome):
    def _fake(bundle):
        return outcome

    return _fake


def _find_scenario(report, scenario_id):
    cap = _get(report, CAPABILITY_ID)
    scenarios = _get(cap, "scenarios")
    for scenario in scenarios:
        if _get(scenario, "id") == scenario_id:
            return cap, scenario
    raise AssertionError(f"scenario {scenario_id} not found in report: {report!r}")


def test_generated_test_failure_fails_scenario_and_writes_file(tmp_path):
    repo_root = tmp_path
    _write_fixture_repo(repo_root)

    rel_path = f"verification/capabilities/{CAPABILITY_ID}/generated-test/test_cs_x_001.py"
    outcome = {
        "model_call_error": None,
        "file": {"path": rel_path, "content": "def test_x():\n    assert False\n"},
    }

    report = capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, judge=None, test_author=_make_test_author(outcome)
    )

    cap, scenario = _find_scenario(report, SCENARIO_ID)
    assert _get(cap, "overall") == "fail"
    assert _get(scenario, "result") == "fail"
    assert (repo_root / rel_path).exists()


def test_generated_test_dotdot_path_fails_and_writes_nothing(tmp_path):
    repo_root = tmp_path
    _write_fixture_repo(repo_root)

    bad_path = "../escape.py"
    outcome = {
        "model_call_error": None,
        "file": {"path": bad_path, "content": "def test_x():\n    assert True\n"},
    }

    report = capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, judge=None, test_author=_make_test_author(outcome)
    )

    _cap, scenario = _find_scenario(report, SCENARIO_ID)
    assert _get(scenario, "result") == "fail"
    assert not (repo_root.parent / "escape.py").exists()
    assert not (repo_root / "escape.py").exists()


def test_generated_test_absolute_path_fails_and_writes_nothing(tmp_path, tmp_path_factory):
    repo_root = tmp_path
    _write_fixture_repo(repo_root)

    other_dir = tmp_path_factory.mktemp("escape-target")
    bad_path = str(other_dir / "escape.py")
    outcome = {
        "model_call_error": None,
        "file": {"path": bad_path, "content": "def test_x():\n    assert True\n"},
    }

    report = capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, judge=None, test_author=_make_test_author(outcome)
    )

    _cap, scenario = _find_scenario(report, SCENARIO_ID)
    assert _get(scenario, "result") == "fail"
    assert not (other_dir / "escape.py").exists()


def test_generated_test_outside_verification_path_fails_and_writes_nothing(tmp_path):
    repo_root = tmp_path
    _write_fixture_repo(repo_root)

    bad_path = "notverification/x.py"
    outcome = {
        "model_call_error": None,
        "file": {"path": bad_path, "content": "def test_x():\n    assert True\n"},
    }

    report = capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, judge=None, test_author=_make_test_author(outcome)
    )

    _cap, scenario = _find_scenario(report, SCENARIO_ID)
    assert _get(scenario, "result") == "fail"
    assert not (repo_root / "notverification" / "x.py").exists()


def test_generated_test_model_call_error_fails(tmp_path):
    repo_root = tmp_path
    _write_fixture_repo(repo_root)

    outcome = {
        "model_call_error": {"category": "network", "message": "boom"},
        "file": None,
    }

    report = capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, judge=None, test_author=_make_test_author(outcome)
    )

    _cap, scenario = _find_scenario(report, SCENARIO_ID)
    assert _get(scenario, "result") == "fail"


def test_generated_test_no_file_fails(tmp_path):
    repo_root = tmp_path
    _write_fixture_repo(repo_root)

    outcome = {"model_call_error": None, "file": None}

    report = capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, judge=None, test_author=_make_test_author(outcome)
    )

    _cap, scenario = _find_scenario(report, SCENARIO_ID)
    assert _get(scenario, "result") == "fail"


def test_generated_test_runs_with_realizing_component_on_pythonpath(tmp_path):
    repo_root = tmp_path
    _write_fixture_repo(
        repo_root, code_files={"foo_mod.py": "def value():\n    return 7\n"}
    )

    rel_path = f"verification/capabilities/{CAPABILITY_ID}/generated-test/test_cs_x_001.py"
    outcome = {
        "model_call_error": None,
        "file": {
            "path": rel_path,
            "content": (
                "def test_x():\n"
                "    import foo_mod\n"
                "    assert foo_mod.value() == 7\n"
            ),
        },
    }

    report = capability_scenario_verifier.run_capability_scenarios(
        [COMPONENT_ID], repo_root, judge=None, test_author=_make_test_author(outcome)
    )

    cap, scenario = _find_scenario(report, SCENARIO_ID)
    assert _get(scenario, "result") == "pass"
    assert _get(cap, "overall") == "pass"