# hotdocs-criterion: sha256:65b30a614d42a4d77109d6387cce97420703867e489a7a343373d8198a80da69
import json
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GHERKIN = (
    "Given a fixture value is 1\n"
    "When the system runs\n"
    "Then the outcome equals 1\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root, slug):
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n",
    )
    _write(
        repo_root / "gen" / slug / (slug + ".py"),
        "def value():\n    return 1\n",
    )


def _build_fixture(repo_root, log_path):
    _component(repo_root, "foo")
    _component(repo_root, "bar")
    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        "FOO_IFACE",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
        "BAR_IFACE",
    )
    _write(repo_root / "specs" / "glossary.md", "GLOSS")

    capability_text = (
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + GHERKIN
        + "```\n"
    )
    capability_path = repo_root / "specs" / "product" / "x.md"
    _write(capability_path, capability_text)

    result_literal = {
        "component_id": "capabilities/P-X",
        "criterion_id": "CS-X-001",
        "model": "m",
        "seed": 3,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
            "content": "def test_x():\n    assert True\n",
        },
        "model_call_error": None,
        "repair_attempts": 0,
        "probe_findings": [],
    }

    fake_author = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "RESULT = " + repr(result_literal) + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    record = {\n"
        "        'bundle': bundle,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'repo_root': str(repo_root),\n"
        "        'backend_id': id(llm_backend),\n"
        "    }\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(record, default=str) + '\\n')\n"
        "    result = dict(RESULT)\n"
        "    result['file'] = dict(RESULT['file'])\n"
        "    result['probe_findings'] = []\n"
        "    return result\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", fake_author)

    fake_endpoint = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        'text': 'PASS',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", fake_endpoint)

    return capability_text


def test_ac_scenario_010_author_test_receives_capability_bundle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author_calls.log"
    capability_text = _build_fixture(repo_root, log_path)

    def sentinel_backend(prompt, model, **params):
        return {
            "text": "PASS",
            "model": model,
            "backend": "sentinel",
            "model_call_error": None,
        }

    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel_backend
    )

    assert log_path.is_file(), "fake author_test was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])

    assert rec["model"] == "m"
    assert rec["seed"] == 3
    assert Path(rec["repo_root"]).resolve() == repo_root.resolve()
    assert rec["backend_id"] == id(sentinel_backend)

    bundle = rec["bundle"]
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] == "P-X"
    assert bundle["criterion_text"].strip() == GHERKIN.strip()
    assert capability_text.strip() in bundle["requirement_text"]
    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface = bundle["interface"]
    i_bar_head = interface.index("## comp-bar")
    i_bar = interface.index("BAR_IFACE")
    i_foo_head = interface.index("## comp-foo")
    i_foo = interface.index("FOO_IFACE")
    assert i_bar_head < i_bar < i_foo_head < i_foo