# hotdocs-criterion: sha256:66f831fb40a66c1a6517f3b9f19e42927bc627f6f724354d05bcfd5be21fe32a
import shutil
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return getattr(value, name, None) is not None


def capability_entry(report, pid):
    if isinstance(report, dict):
        return report[pid]
    try:
        return report[pid]
    except TypeError:
        return getattr(report, "capabilities")[pid]


def _live_repo_root():
    gen = next(
        p
        for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    return gen.parent


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root, slug, pid, scenarios_text, log_path):
    # Component realizing the capability.
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " component\n"
        + "status: draft\n"
        + "owners: [tester]\n"
        + "realizes: [" + pid + "]\n"
        + "sealed: false\n"
        + "---\n\n"
        + "# comp-" + slug + "\n\n"
        + "A fixture component.\n",
    )
    module_name = slug.replace("-", "_")
    _write(
        repo_root / "gen" / slug / (module_name + ".py"),
        "def f():\n    return 1\n",
    )

    # The capability, with its scenarios nested inline.
    _write(
        repo_root / "specs" / "product" / (slug + "-capability.md"),
        "---\n"
        + "id: " + pid + "\n"
        + "title: " + pid + " capability\n"
        + "status: draft\n"
        + "owners: [tester]\n"
        + "---\n\n"
        + "# " + pid + "\n\n"
        + "A fixture capability.\n\n"
        + scenarios_text,
    )

    # Fake test-author module, real signature and full result shape.
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = 'generated_test@1.1.0'\n"
        + "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "\n"
        + "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        + "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        + "        fh.write('module_author_test ' + str(bundle['criterion_id']) + '\\n')\n"
        + "    cid = str(bundle['criterion_id'])\n"
        + "    pid = 'P-' + cid[len('CS-'):].rsplit('-', 1)[0]\n"
        + "    name = 'test_' + cid.lower().replace('-', '_') + '.py'\n"
        + "    return {\n"
        + "        'component_id': 'comp-capability',\n"
        + "        'criterion_id': cid,\n"
        + "        'model': model,\n"
        + "        'seed': seed,\n"
        + "        'prompt_version': 'v1',\n"
        + "        'cache_hit': False,\n"
        + "        'file': {\n"
        + "            'path': 'verification/capabilities/' + pid + '/generated-test/' + name,\n"
        + "            'content': 'def test_x():\\n    assert True\\n',\n"
        + "        },\n"
        + "        'model_call_error': None,\n"
        + "    }\n",
    )

    # Fake llm-endpoint module, real signature and full ModelResponse shape.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "\n"
        + "def complete(prompt, model, *, backend=None, **params):\n"
        + "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        + "        fh.write('module_complete\\n')\n"
        + "    return {\n"
        + "        'text': 'fail: because',\n"
        + "        'model': model,\n"
        + "        'backend': 'fake',\n"
        + "        'model_call_error': None,\n"
        + "    }\n",
    )

    # The real compiler, copied from the live repository.
    src = _live_repo_root() / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def _scenario(sid, pid, kind):
    return (
        "### " + sid + "\n\n"
        + "Covers: " + pid + "\n"
        + "Kind: " + kind + "\n\n"
        + "```gherkin\n"
        + "Given the assembled system\n"
        + "When a user exercises the capability\n"
        + "Then the capability behaves as described\n"
        + "```\n\n"
    )


def _make_test_author(log_path):
    def test_author(bundle):
        sid = bundle["scenario_id"] if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("injected_test_author " + str(sid) + "\n")
        pid = "P-" + str(sid)[len("CS-"):].rsplit("-", 1)[0]
        name = "test_" + str(sid).lower().replace("-", "_") + ".py"
        return {
            "component_id": "comp-capability",
            "criterion_id": sid,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/capabilities/" + pid + "/generated-test/" + name,
                "content": "def test_x():\n    assert True\n",
            },
            "model_call_error": None,
        }

    return test_author


def _make_failing_judge(log_path):
    def judge(bundle):
        sid = bundle["scenario_id"] if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("injected_judge " + str(sid) + "\n")
        return {"result": "fail", "rationale": "because"}

    return judge


def test_mixed_scenarios_report_per_scenario_with_rationale_only_on_judge(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    pid = "P-MIX"
    scenarios = _scenario("CS-MIX-001", pid, "generated-test") + _scenario(
        "CS-MIX-002", pid, "llm-judge"
    )
    _build_repo(repo_root, "alpha", pid, scenarios, log_path)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha"],
        repo_root,
        judge=_make_failing_judge(log_path),
        test_author=_make_test_author(log_path),
    )

    cap = capability_entry(report, pid)
    entries = list(field(cap, "scenarios"))
    assert len(entries) == 2

    by_id = {field(e, "id"): e for e in entries}
    assert set(by_id) == {"CS-MIX-001", "CS-MIX-002"}

    gen_entry = by_id["CS-MIX-001"]
    judge_entry = by_id["CS-MIX-002"]

    assert field(gen_entry, "kind") == "generated-test"
    assert not has_field(gen_entry, "rationale")

    assert field(judge_entry, "kind") == "llm-judge"
    assert field(judge_entry, "result") == "fail"
    assert field(judge_entry, "rationale") == "because"

    assert field(cap, "overall") == "fail"

    log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert "injected_test_author CS-MIX-001" in log
    assert "injected_judge CS-MIX-002" in log


def test_capability_with_no_scenarios_fails_with_empty_list(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    pid = "P-EMPTY"
    _build_repo(repo_root, "beta", pid, "No scenarios are declared here.\n", log_path)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-beta"],
        repo_root,
        judge=_make_failing_judge(log_path),
        test_author=_make_test_author(log_path),
    )

    cap = capability_entry(report, pid)
    assert field(cap, "overall") == "fail"
    assert list(field(cap, "scenarios")) == []


def test_only_llm_judge_scenario_without_judge_is_skipped(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    pid = "P-SOLO"
    _build_repo(repo_root, "gamma", pid, _scenario("CS-SOLO-001", pid, "llm-judge"), log_path)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-gamma"],
        repo_root,
        judge=None,
        test_author=_make_test_author(log_path),
    )

    cap = capability_entry(report, pid)
    entries = list(field(cap, "scenarios"))
    assert len(entries) == 1
    entry = entries[0]
    assert field(entry, "id") == "CS-SOLO-001"
    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped"
    assert field(cap, "overall") == "skipped"