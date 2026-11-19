# hotdocs-criterion: sha256:6e02c08c3123ab72f22c5e8de39f1a8ee83829792384d7adaccb04874a08ffec
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return getattr(value, name, None) is not None


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def plant_python_adapter(repo_root):
    src = (
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n"
    )
    write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def plant_fake_dependencies(repo_root):
    passing = "def test_x():\n    assert True\n"
    ta = (
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    cid = bundle[\"criterion_id\"]\n"
        "    name = \"test_\" + cid.lower().replace(\"-\", \"_\") + \".py\"\n"
        "    return {\n"
        "        \"component_id\": bundle.get(\"component_id\", \"\"),\n"
        "        \"criterion_id\": cid,\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\"path\": \"verification/capabilities/fake/generated-test/\" + name,\n"
        "                 \"content\": " + repr(passing) + "},\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n"
    )
    write(repo_root / "gen" / "test-author" / "test_author.py", ta)
    reply = '{"result": "pass", "rationale": "fake"}'
    le = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": " + repr(reply) + ", \"model\": model,\n"
        "            \"backend\": \"fake\", \"model_call_error\": None}\n"
    )
    write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", le)


def plant_component(repo_root, slug, capability_id):
    text = (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: [" + capability_id + "]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + slug + "\n"
    )
    write(repo_root / "specs" / "components" / slug / "component.md", text)
    module = slug.replace("-", "_")
    write(repo_root / "gen" / slug / (module + ".py"), "VALUE = 1\n")


def scenario_section(scenario_id, capability_id, kind):
    return (
        "### " + scenario_id + "\n"
        "\n"
        "Covers: " + capability_id + "\n"
        "Kind: " + kind + "\n"
        "\n"
        "```gherkin\n"
        "Given the system is assembled\n"
        "When the capability is exercised\n"
        "Then it behaves as described\n"
        "```\n"
        "\n"
    )


def plant_capability(repo_root, name, capability_id, sections):
    text = (
        "---\n"
        "id: " + capability_id + "\n"
        "title: " + name + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# " + name + "\n"
        "\n"
        "Capability description.\n"
        "\n"
    )
    for section in sections:
        text += section
    write(repo_root / "specs" / "product" / (name + ".md"), text)


def base_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_python_adapter(repo_root)
    plant_fake_dependencies(repo_root)
    return repo_root


def capability_entry(report, capability_id):
    if isinstance(report, dict):
        return report[capability_id]
    return getattr(report, capability_id)


def test_generated_test_and_llm_judge_scenarios(tmp_path):
    repo_root = base_repo(tmp_path)
    plant_component(repo_root, "alpha", "P-ALPHA")
    plant_capability(
        repo_root,
        "alpha",
        "P-ALPHA",
        [
            scenario_section("CS-ALPHA-001", "P-ALPHA", "generated-test"),
            scenario_section("CS-ALPHA-002", "P-ALPHA", "llm-judge"),
        ],
    )

    log = tmp_path / "calls.log"

    def fake_test_author(bundle):
        sid = bundle.get("scenario_id") if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        with open(log, "a") as fh:
            fh.write("test_author " + str(sid) + "\n")
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-ALPHA/generated-test/test_cs_alpha_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    def fake_judge(bundle):
        sid = bundle.get("scenario_id") if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        with open(log, "a") as fh:
            fh.write("judge " + str(sid) + "\n")
        return {"result": "fail", "rationale": "because"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-alpha"], repo_root, judge=fake_judge, test_author=fake_test_author
    )

    entry = capability_entry(report, "P-ALPHA")
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 2

    by_id = {field(s, "id"): s for s in scenarios}
    assert set(by_id) == {"CS-ALPHA-001", "CS-ALPHA-002"}

    generated = by_id["CS-ALPHA-001"]
    judged = by_id["CS-ALPHA-002"]
    assert field(generated, "kind") == "generated-test"
    assert field(judged, "kind") == "llm-judge"

    assert not has_field(generated, "rationale")
    assert field(judged, "rationale") == "because"

    assert field(entry, "overall") == "fail"


def test_capability_without_scenarios_fails(tmp_path):
    repo_root = base_repo(tmp_path)
    plant_component(repo_root, "beta", "P-BETA")
    plant_capability(repo_root, "beta", "P-BETA", [])

    report = capability_scenario_verifier.run_capability_scenarios(["comp-beta"], repo_root)

    entry = capability_entry(report, "P-BETA")
    assert field(entry, "overall") == "fail"
    assert list(field(entry, "scenarios")) == []


def test_llm_judge_only_without_judge_is_skipped(tmp_path):
    repo_root = base_repo(tmp_path)
    plant_component(repo_root, "gamma", "P-GAMMA")
    plant_capability(
        repo_root,
        "gamma",
        "P-GAMMA",
        [scenario_section("CS-GAMMA-001", "P-GAMMA", "llm-judge")],
    )

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-gamma"], repo_root, judge=None
    )

    entry = capability_entry(report, "P-GAMMA")
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    only = scenarios[0]
    assert field(only, "id") == "CS-GAMMA-001"
    assert field(only, "result") == "skipped"
    assert field(entry, "overall") == "skipped"