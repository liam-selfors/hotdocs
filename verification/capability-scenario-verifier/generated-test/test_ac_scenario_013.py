# hotdocs-criterion: sha256:2fa04bbb133784665bd39ff7c450cd161ffde89a6c48a2b77e0d826f13607573
"""AC-SCENARIO-013 (covers R-SCENARIO-005).

A generated-test scenario is decided by running its test with the run
environment's interpreter. When the python adapter's provision reports
ok False, no test runs and the scenario is a fail.
"""

import os
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SCENARIO_ID = "CS-X-001"
TEST_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


ADAPTER_OK = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": str(Path(repo_root) / \"pywrap\")}\n"
)

ADAPTER_FAIL = (
    "import sys\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": False, \"reason\": \"python environment: no lock\", \"versions\": {},\n"
    "            \"lockfile_sha256\": None, \"interpreter\": None}\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_fixture(repo_root, adapter_ok):
    # Planted python adapter.
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        ADAPTER_OK if adapter_ok else ADAPTER_FAIL,
    )

    # Planted wrapper interpreter.
    pywrap = repo_root / "pywrap"
    pywrap.write_text(
        "#!/bin/sh\n"
        "HOTDOCS_WRAPPED=1 exec '" + sys.executable + "' \"$@\"\n"
    )
    os.chmod(pywrap, 0o755)

    # A component realizing P-X.
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
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven a value is 1\nThen value equals 1\n```\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo():\n    return 1\n")

    # The capability with one generated-test scenario.
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
        "### " + SCENARIO_ID + "\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the wrapped interpreter\n"
        "When the test runs\n"
        "Then it sees HOTDOCS_WRAPPED\n"
        "```\n",
    )

    # Fake test-author and llm-endpoint modules (not expected to be used,
    # since test_author is injected and the scenario is not llm-judge).
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


def _make_test_author(content):
    def test_author(bundle):
        return {
            "model_call_error": None,
            "file": {"path": TEST_PATH, "content": content},
        }

    return test_author


def _scenario_result(report):
    entry = field(report, "P-X")
    scenarios = field(entry, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == SCENARIO_ID]
    assert len(matches) == 1, scenarios
    return field(matches[0], "result")


def test_generated_test_runs_under_environment_interpreter(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, adapter_ok=True)

    content = (
        "import os\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert os.environ.get('HOTDOCS_WRAPPED') == '1'\n"
    )
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=_make_test_author(content)
    )
    assert _scenario_result(report) == "pass"


def test_provision_not_ok_fails_without_running(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, adapter_ok=False)

    ran = repo_root / "ran.txt"
    content = (
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    Path(" + repr(str(ran)) + ").write_text('ran')\n"
        "    Path('ran.txt').write_text('ran')\n"
        "    assert os.environ.get('HOTDOCS_WRAPPED') == '1'\n"
    )
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=_make_test_author(content)
    )
    assert _scenario_result(report) == "fail"
    assert not ran.exists()