# hotdocs-criterion: sha256:de1eec5bff8d83f94d2d9df35f66e68267f32417fd4c7f356ec257f3973d67c4
import os
import sys
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
    except (TypeError, KeyError):
        return getattr(report, pid)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


KIND_PYTHON_SRC = (
    "import sys\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": sys.executable}\n"
)

FAKE_TEST_AUTHOR_SRC = (
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    cid = bundle[" + repr("criterion_id") + "]\n"
    "    name = 'test_' + cid.lower().replace('-', '_') + '.py'\n"
    "    return {\n"
    "        'component_id': 'P-X',\n"
    "        'criterion_id': cid,\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'file': {'path': 'verification/capabilities/P-X/generated-test/' + name,\n"
    "                 'content': " + repr("def test_x():\n    assert True\n") + "},\n"
    "        'model_call_error': None,\n"
    "        'repair_attempts': 0,\n"
    "        'probe_findings': [],\n"
    "    }\n"
)

FAKE_LLM_ENDPOINT_SRC = (
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    return {'text': " + repr('{"result": "pass", "rationale": "ok"}') + ",\n"
    "            'model': model, 'backend': 'fake', 'model_call_error': None}\n"
)


def build_repo(repo_root, scenarios):
    """scenarios: list of (scenario_id, kind)."""
    repo_root = Path(repo_root)
    write(repo_root / "gen" / "kind-python" / "kind_python.py", KIND_PYTHON_SRC)
    write(repo_root / "gen" / "test-author" / "test_author.py", FAKE_TEST_AUTHOR_SRC)
    write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT_SRC)

    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    write(repo_root / "gen" / "foo" / "foo.py", "def hello():\n    return 1\n")

    text = (
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
    )
    for sid, kind in scenarios:
        text += (
            "### " + sid + "\n"
            "\n"
            "Covers: P-X\n"
            "Kind: " + kind + "\n"
            "\n"
            "```gherkin\n"
            "Given a foo is 1\n"
            "When the system runs\n"
            "Then the result equals 1\n"
            "```\n"
            "\n"
        )
    write(repo_root / "specs" / "product" / "x.md", text)
    return repo_root


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a") as fh:
            fh.write("called\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }
    return test_author


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a") as fh:
            fh.write("judged\n")
        return {"result": "fail", "rationale": "because"}
    return judge


def test_generated_test_and_failing_llm_judge(tmp_path):
    repo_root = build_repo(
        tmp_path / "repo",
        [("CS-X-001", "generated-test"), ("CS-X-002", "llm-judge")],
    )
    log_path = tmp_path / "calls.log"

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"],
        repo_root,
        judge=make_judge(log_path),
        test_author=make_test_author(log_path),
    )

    entry = capability_entry(report, "P-X")
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 2

    by_kind = {field(s, "kind"): s for s in scenarios}
    assert set(by_kind) == {"generated-test", "llm-judge"}

    gen_entry = by_kind["generated-test"]
    assert field(gen_entry, "id") == "CS-X-001"
    assert not has_field(gen_entry, "rationale")

    judge_entry = by_kind["llm-judge"]
    assert field(judge_entry, "id") == "CS-X-002"
    assert field(judge_entry, "rationale") == "because"

    assert field(entry, "overall") == "fail"


def test_capability_with_no_scenarios_fails(tmp_path):
    repo_root = build_repo(tmp_path / "repo", [])

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root
    )

    entry = capability_entry(report, "P-X")
    assert field(entry, "overall") == "fail"
    assert list(field(entry, "scenarios")) == []


def test_llm_judge_without_judge_is_skipped(tmp_path):
    repo_root = build_repo(tmp_path / "repo", [("CS-X-001", "llm-judge")])

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None
    )

    entry = capability_entry(report, "P-X")
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-X-001"
    assert field(scenarios[0], "result") == "skipped"
    assert field(entry, "overall") == "skipped"