# hotdocs-criterion: sha256:eba33a9fdcbc2a1719b1d88436aa3e1d601f501d63855a2a20a24dae15bef3d0
import sys
from collections.abc import Mapping
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def report_keys(report):
    if isinstance(report, Mapping):
        return set(report.keys())
    return set(report.keys())


def report_entry(report, key):
    return report[key]


def write(path, text):
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
    "    cid = bundle[\"criterion_id\"]\n"
    "    name = \"test_\" + cid.lower().replace(\"-\", \"_\") + \".py\"\n"
    "    return {\n"
    "        \"component_id\": \"\",\n"
    "        \"criterion_id\": cid,\n"
    "        \"model\": model,\n"
    "        \"seed\": seed,\n"
    "        \"prompt_version\": \"v1\",\n"
    "        \"cache_hit\": False,\n"
    "        \"file\": {\"path\": \"verification/capabilities/\" + bundle.get(\"covers\", \"P-X\") + \"/generated-test/\" + name,\n"
    "                 \"content\": \"def test_x():\\n    assert True\\n\"},\n"
    "        \"model_call_error\": None,\n"
    "        \"repair_attempts\": 0,\n"
    "        \"probe_findings\": [],\n"
    "    }\n"
)

FAKE_LLM_ENDPOINT_SRC = (
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\",\n"
    "            \"model_call_error\": None}\n"
)


def base_repo(repo_root):
    write(repo_root / "gen" / "kind-python" / "kind_python.py", KIND_PYTHON_SRC)
    write(repo_root / "gen" / "test-author" / "test_author.py", FAKE_TEST_AUTHOR_SRC)
    write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT_SRC)
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")


def component_md(slug, realizes=None, sealed=False, source_path=None):
    text = (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
    )
    if realizes is not None:
        text += "realizes: [" + ", ".join(realizes) + "]\n"
    if sealed:
        text += "sealed: true\n"
        text += "source_path: " + source_path + "\n"
    else:
        text += "sealed: false\n"
    text += "---\n\n# " + slug + "\n"
    return text


def capability_md(pid, scenario_id):
    return (
        "---\n"
        "id: " + pid + "\n"
        "title: " + pid + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# " + pid + "\n"
        "\n"
        "### " + scenario_id + "\n"
        "\n"
        "Covers: " + pid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a repository\n"
        "When the capability is exercised\n"
        "Then it works\n"
        "```\n"
    )


def make_test_author(log_path, contents_by_scenario):
    def test_author(bundle):
        sid = field(bundle, "scenario_id")
        cap = field(bundle, "capability_id")
        with open(log_path, "a") as fh:
            fh.write(sid + "\n")
        name = "test_" + sid.lower().replace("-", "_") + ".py"
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/" + cap + "/generated-test/" + name,
                "content": contents_by_scenario.get(
                    sid, "def test_x():\n    assert True\n"
                ),
            },
        }

    return test_author


def test_report_only_has_capabilities_realized_in_blast_radius(tmp_path):
    repo_root = tmp_path / "repo"
    base_repo(repo_root)

    write(repo_root / "specs" / "components" / "foo" / "component.md",
          component_md("foo", realizes=["P-ZERO-EDIT"]))
    write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    write(repo_root / "specs" / "components" / "bar" / "component.md",
          component_md("bar"))
    write(repo_root / "gen" / "bar" / "bar.py", "VALUE = 2\n")

    write(repo_root / "specs" / "product" / "zero-edit.md",
          capability_md("P-ZERO-EDIT", "CS-ZERO-EDIT-001"))
    write(repo_root / "specs" / "product" / "unrelated.md",
          capability_md("P-UNRELATED", "CS-UNRELATED-001"))

    log_path = tmp_path / "author.log"
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"],
        repo_root,
        judge=None,
        test_author=make_test_author(log_path, {}),
    )

    assert report_keys(report) == {"P-ZERO-EDIT"}


def test_sealed_component_code_directory_is_source_path(tmp_path):
    repo_root = tmp_path / "repo"
    base_repo(repo_root)

    write(repo_root / "specs" / "components" / "baz" / "component.md",
          component_md("baz", realizes=["P-SEALED"], sealed=True,
                        source_path="pipeline/baz/"))
    write(repo_root / "pipeline" / "baz" / "baz.py", "SEALED_VALUE = 4242\n")
    assert not (repo_root / "gen" / "baz").exists()

    write(repo_root / "specs" / "product" / "sealed.md",
          capability_md("P-SEALED", "CS-SEALED-001"))

    content = (
        "import baz\n"
        "\n"
        "\n"
        "def test_sealed_import():\n"
        "    assert baz.SEALED_VALUE == 4242\n"
    )
    log_path = tmp_path / "author.log"
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"],
        repo_root,
        judge=None,
        test_author=make_test_author(log_path, {"CS-SEALED-001": content}),
    )

    assert log_path.is_file()
    assert "CS-SEALED-001" in log_path.read_text().split()

    assert report_keys(report) == {"P-SEALED"}
    entry = report_entry(report, "P-SEALED")
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-SEALED-001"
    assert field(scenarios[0], "result") == "pass"
    assert field(entry, "overall") == "pass"