# hotdocs-criterion: sha256:98e220d462d48c30759a9d9f087c3c20f209bdc91618a32eaf50a22a736b86ba
import os
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


TEST_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def _build_repo(repo_root, provision_ok):
    repo_root = Path(repo_root)

    # A realizing component, unsealed, with its code under gen/<slug>/.
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
    _write(repo_root / "gen" / "foo" / "foo.py", "def value():\n    return 1\n")

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
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo component\n"
        "When the value is read\n"
        "Then the value is 1\n"
        "```\n",
    )

    # The planted wrapper interpreter.
    pywrap = repo_root / "pywrap"
    _write(
        pywrap,
        "#!/bin/sh\n"
        "HOTDOCS_WRAPPED=1 exec '" + sys.executable + "' \"$@\"\n",
    )
    os.chmod(pywrap, 0o755)

    # The planted python adapter.
    if provision_ok:
        adapter = (
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "KIND = 'python'\n"
            "\n"
            "\n"
            "def provision(repo_root):\n"
            "    return {'ok': True, 'reason': '', 'versions': {}, 'lockfile_sha256': None,\n"
            "            'interpreter': str(Path(repo_root) / 'pywrap')}\n"
        )
    else:
        adapter = (
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "KIND = 'python'\n"
            "\n"
            "\n"
            "def provision(repo_root):\n"
            "    return {'ok': False, 'reason': 'python environment: no lock', 'versions': {},\n"
            "            'lockfile_sha256': None, 'interpreter': None}\n"
        )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", adapter)

    # Fake test-author and llm-endpoint dependencies (unused: test_author is injected).
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': " + repr(TEST_PATH) + ",\n"
        "                 'content': 'def test_x():\\n    assert True\\n'},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, backend=None, **params):\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n",
    )


def _make_test_author(content):
    def test_author(bundle):
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

    return test_author


def _scenario_result(report):
    entry = field(report, "P-X") if not isinstance(report, dict) else report["P-X"]
    scenarios = field(entry, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    return field(matching[0], "result")


def test_wrapped_interpreter_runs_generated_test(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, provision_ok=True)

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


def test_provision_not_ok_fails_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_WRAPPED", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, provision_ok=False)

    ran = repo_root / "ran.txt"
    content = (
        "import os\n"
        "\n"
        "open(" + repr(str(ran)) + ", 'w').write('ran')\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    open(" + repr(str(ran)) + ", 'w').write('ran')\n"
        "    assert os.environ.get('HOTDOCS_WRAPPED') == '1'\n"
    )
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=_make_test_author(content)
    )
    assert _scenario_result(report) == "fail"
    assert not ran.exists()