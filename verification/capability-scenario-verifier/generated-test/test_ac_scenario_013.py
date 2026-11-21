# hotdocs-criterion: sha256:10b55dc3d9bec15a9b719f7ab102187e97d56c1d45296af1d442a59abaa34374
import os
import sys
from pathlib import Path

import capability_scenario_verifier


TEST_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _adapter_source(ok):
    if ok:
        return (
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "\n"
            "def provision(repo_root):\n"
            "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, "
            "\"lockfile_sha256\": None,\n"
            "            \"interpreter\": str(Path(repo_root) / \"pywrap\")}\n"
        )
    return (
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": False, \"reason\": \"python environment: no lock\", "
        "\"versions\": {},\n"
        "            \"lockfile_sha256\": None, \"interpreter\": None}\n"
    )


def _build_repo(repo_root, ok):
    repo_root = Path(repo_root)

    # Component realizing P-X
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")

    # Capability with one generated-test scenario
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )

    # Planted python adapter
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", _adapter_source(ok))

    # Planted wrapper interpreter
    pywrap = repo_root / "pywrap"
    pywrap.write_text(
        "#!/bin/sh\n"
        + "HOTDOCS_WRAPPED=1 exec '" + sys.executable + "' \"$@\"\n"
    )
    os.chmod(str(pywrap), 0o755)

    # Fake dependencies (not expected to be used: test_author is injected)
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        \"component_id\": \"comp-foo\",\n"
        "        \"criterion_id\": bundle[\"criterion_id\"],\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\"path\": " + repr(TEST_PATH) + ",\n"
        "                 \"content\": \"def test_x():\\n    assert True\\n\"},\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )


def _make_author(content, log_path):
    def author(bundle):
        with open(str(log_path), "a") as fh:
            fh.write("called\n")
        return {
            "component_id": "comp-foo",
            "criterion_id": "CS-X-001",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": TEST_PATH, "content": content},
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def _scenario_result(report):
    entry = report["P-X"] if isinstance(report, dict) else getattr(report, "P-X")
    scenarios = field(entry, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    return field(matching[0], "result")


def test_wrapped_interpreter_runs_generated_test(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, ok=True)

    content = (
        "import os\n"
        "\n"
        "\n"
        "def test_wrapped():\n"
        "    assert os.environ.get(\"HOTDOCS_WRAPPED\") == \"1\"\n"
    )
    log_path = tmp_path / "author.log"
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=_make_author(content, log_path)
    )

    assert _scenario_result(report) == "pass"


def test_provision_not_ok_fails_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, ok=False)

    ran_path = repo_root / "ran.txt"
    content = (
        "import os\n"
        "\n"
        "\n"
        "def test_wrapped():\n"
        "    with open(" + repr(str(ran_path)) + ", \"w\") as fh:\n"
        "        fh.write(\"ran\")\n"
        "    assert os.environ.get(\"HOTDOCS_WRAPPED\") == \"1\"\n"
    )
    log_path = tmp_path / "author.log"
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=_make_author(content, log_path)
    )

    assert _scenario_result(report) == "fail"
    assert not ran_path.exists()