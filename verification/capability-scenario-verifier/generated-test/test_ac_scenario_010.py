# hotdocs-criterion: sha256:1ff6fd20b16645c6f229b51856ed0d252a22af5706256b6029894a57a6a5fa0f
import json
from pathlib import Path

import capability_scenario_verifier


GHERKIN = "Given a thing exists\nWhen it is used\nThen it works"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _SentinelBackend:
    def __call__(self, prompt, model, **params):
        return {
            "text": "",
            "model": model,
            "backend": "sentinel",
            "model_call_error": None,
        }

    def __repr__(self):
        return "SENTINEL_BACKEND"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component_md(slug, title):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "A fixture component.\n"
    )


def _build_fixture(repo_root, log_path):
    # Components
    _write(repo_root / "specs" / "components" / "foo" / "component.md",
           _component_md("foo", "Foo"))
    _write(repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
           "FOO_IFACE\n")
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo():\n    return 1\n")

    _write(repo_root / "specs" / "components" / "bar" / "component.md",
           _component_md("bar", "Bar"))
    _write(repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
           "BAR_IFACE\n")
    _write(repo_root / "gen" / "bar" / "bar.py", "def bar():\n    return 2\n")

    # Glossary
    _write(repo_root / "specs" / "glossary.md", "GLOSS")

    # Capability
    cap_text = (
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
        + GHERKIN + "\n"
        "```\n"
    )
    _write(repo_root / "specs" / "product" / "x.md", cap_text)

    # Fake test-author
    fake_author = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    record = {\n"
        "        'bundle': bundle,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'repo_root': str(repo_root),\n"
        "        'backend_id': id(llm_backend),\n"
        "        'backend_repr': repr(llm_backend),\n"
        "    }\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps(record, default=str) + '\\n')\n"
        "    return {\n"
        "        'component_id': 'capabilities/P-X',\n"
        "        'criterion_id': 'CS-X-001',\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': 'verification/capabilities/P-X/generated-test/test_cs_x_001.py',\n"
        "            'content': 'def test_x():\\n    assert True\\n',\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", fake_author)

    # Fake llm-endpoint (not expected to be used for a generated-test scenario)
    fake_endpoint = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        'text': 'pass',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", fake_endpoint)

    return cap_text


def test_run_capability_gates_builds_author_test_bundle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author_calls.log"
    cap_text = _build_fixture(repo_root, log_path)

    sentinel = _SentinelBackend()

    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel
    )

    assert log_path.is_file(), "fake author_test was never called"
    lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1, "author_test called " + str(len(lines)) + " times"
    call = json.loads(lines[0])

    assert call["model"] == "m"
    assert call["seed"] == 3
    assert Path(call["repo_root"]).resolve() == repo_root.resolve()
    assert call["backend_id"] == id(sentinel)
    assert call["backend_repr"] == "SENTINEL_BACKEND"

    bundle = call["bundle"]
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    covers = bundle["covers"]
    assert covers == "P-X" or covers == ["P-X"], covers
    assert bundle["criterion_text"].strip() == GHERKIN
    assert cap_text.strip() in bundle["requirement_text"]
    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface = bundle["interface"]
    i_bar_head = interface.find("## comp-bar")
    assert i_bar_head != -1, interface
    i_bar_iface = interface.find("BAR_IFACE", i_bar_head)
    assert i_bar_iface != -1, interface
    i_foo_head = interface.find("## comp-foo", i_bar_iface)
    assert i_foo_head != -1, interface
    i_foo_iface = interface.find("FOO_IFACE", i_foo_head)
    assert i_foo_iface != -1, interface
    assert i_bar_head < i_bar_iface < i_foo_head < i_foo_iface