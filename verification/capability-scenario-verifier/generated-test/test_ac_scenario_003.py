# hotdocs-criterion: sha256:4c4395c0fbe09a2af2394d79674930e5b01f4bf642c8d3bad45e4b4b99b30993
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def capability_entry(report, pid):
    if isinstance(report, dict):
        return report[pid]
    try:
        return report[pid]
    except (TypeError, KeyError):
        return getattr(report, pid)


def has_rationale(entry):
    if isinstance(entry, dict):
        return "rationale" in entry
    return getattr(entry, "rationale", None) is not None


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def plant_common(repo_root):
    # The planted python adapter, so no criterion depends on the tool's own.
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # Fake test-author dependency, matching author_test's documented signature
    # and TestAuthoringResult shape.
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    cid = bundle[\"criterion_id\"]\n"
        "    name = \"test_\" + cid.lower().replace(\"-\", \"_\") + \".py\"\n"
        "    return {\n"
        "        \"component_id\": \"P-X\",\n"
        "        \"criterion_id\": cid,\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\n"
        "            \"path\": \"verification/capabilities/P-X/generated-test/\" + name,\n"
        "            \"content\": " + repr("def test_x():\n    assert True\n") + ",\n"
        "        },\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )

    # Fake llm-endpoint dependency, matching complete's documented signature
    # and ModelResponse shape.
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        \"text\": " + repr('{"result": "fail", "rationale": "unused"}') + ",\n"
        "        \"model\": model,\n"
        "        \"backend\": \"fake\",\n"
        "        \"model_call_error\": None,\n"
        "    }\n",
    )

    # A component realizing P-X.
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    write(repo_root / "gen" / "foo" / "foo.py", "def foo():\n    return 1\n")


def scenario_section(scenario_id, kind):
    return (
        "### " + scenario_id + "\n"
        "\n"
        "Covers: P-X\n"
        "Kind: " + kind + "\n"
        "\n"
        "```gherkin\n"
        "Given the system is assembled\n"
        "When a user does the thing\n"
        "Then the thing is done\n"
        "```\n"
        "\n"
    )


def write_capability(repo_root, sections):
    write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "A fixture capability.\n"
        "\n"
        "## Scenarios\n"
        "\n" + "".join(sections),
    )


def make_logger(log_path):
    def log(line):
        with open(log_path, "a") as fh:
            fh.write(line + "\n")
    return log


def test_generated_test_pass_and_llm_judge_fail_gives_overall_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_common(repo_root)
    write_capability(
        repo_root,
        [
            scenario_section("CS-X-001", "generated-test"),
            scenario_section("CS-X-002", "llm-judge"),
        ],
    )

    author_log = tmp_path / "author.log"
    judge_log = tmp_path / "judge.log"
    log_author = make_logger(author_log)
    log_judge = make_logger(judge_log)

    def fake_test_author(bundle):
        sid = bundle["scenario_id"] if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        log_author(str(sid))
        name = "test_" + str(sid).lower().replace("-", "_") + ".py"
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/" + name,
                "content": "def test_x():\n    assert True\n",
            },
        }

    def fake_judge(bundle):
        sid = bundle["scenario_id"] if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        log_judge(str(sid))
        return {"result": "fail", "rationale": "because"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=fake_judge, test_author=fake_test_author
    )

    cap = capability_entry(report, "P-X")
    scenarios = list(field(cap, "scenarios"))
    assert len(scenarios) == 2

    by_kind = {field(s, "kind"): s for s in scenarios}
    assert set(by_kind) == {"generated-test", "llm-judge"}

    gen_entry = by_kind["generated-test"]
    assert field(gen_entry, "id") == "CS-X-001"
    assert field(gen_entry, "result") == "pass"
    assert not has_rationale(gen_entry)

    judge_entry = by_kind["llm-judge"]
    assert field(judge_entry, "id") == "CS-X-002"
    assert field(judge_entry, "result") == "fail"
    assert field(judge_entry, "rationale") == "because"

    assert field(cap, "overall") == "fail"

    assert author_log.read_text().splitlines() == ["CS-X-001"]
    assert judge_log.read_text().splitlines() == ["CS-X-002"]


def test_capability_with_no_scenarios_fails_with_empty_list(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_common(repo_root)
    write_capability(repo_root, ["No scenarios are declared here.\n"])

    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    def fake_judge(bundle):
        return {"result": "pass", "rationale": "ok"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=fake_judge, test_author=fake_test_author
    )

    cap = capability_entry(report, "P-X")
    assert list(field(cap, "scenarios")) == []
    assert field(cap, "overall") == "fail"


def test_only_llm_judge_without_judge_is_skipped(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_common(repo_root)
    write_capability(repo_root, [scenario_section("CS-X-001", "llm-judge")])

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root
    )

    cap = capability_entry(report, "P-X")
    scenarios = list(field(cap, "scenarios"))
    assert len(scenarios) == 1
    entry = scenarios[0]
    assert field(entry, "id") == "CS-X-001"
    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped"
    assert field(cap, "overall") == "skipped"