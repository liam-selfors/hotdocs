# hotdocs-criterion: sha256:89f31cfc65b0d0fb4581e1ae4afb92b6535223c08443d13e0e6c4f5f6780ca7e
import json
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GHERKIN = (
    "Given the assembled system is ready\n"
    "When the scenario runs\n"
    "Then the outcome is observed\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root, slug, iface_text):
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "interface" / "library.md",
        iface_text,
    )
    module_name = slug.replace("-", "_")
    _write(
        repo_root / "gen" / slug / (module_name + ".py"),
        "def value():\n    return " + repr(slug) + "\n",
    )


def _build_fixture(repo_root, log_path):
    _component(repo_root, "foo", "FOO_IFACE")
    _component(repo_root, "bar", "BAR_IFACE")
    _write(repo_root / "specs" / "glossary.md", "GLOSS")

    product_text = (
        "---\n"
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n" + GHERKIN + "```\n"
    )
    product_path = repo_root / "specs" / "product" / "x.md"
    _write(product_path, product_text)

    # Planted python adapter.
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # Fake test-author.
    rel_path = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
    content = "def test_x():\n    assert True\n"
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REL_PATH = " + repr(rel_path) + "\n"
        "CONTENT = " + repr(content) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    record = {\n"
        "        \"bundle\": dict(bundle),\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"repo_root\": None if repo_root is None else str(repo_root),\n"
        "        \"backend_id\": id(llm_backend),\n"
        "        \"backend_is_none\": llm_backend is None,\n"
        "    }\n"
        "    with open(LOG_PATH, \"a\", encoding=\"utf-8\") as fh:\n"
        "        fh.write(json.dumps(record) + \"\\n\")\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / REL_PATH\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(CONTENT, encoding=\"utf-8\")\n"
        "    return {\"model_call_error\": None,\n"
        "            \"file\": {\"path\": REL_PATH, \"content\": CONTENT}}\n",
    )

    # Fake llm-endpoint.
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"PASS\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )
    return product_text


class _SentinelBackend:
    def __call__(self, prompt, model, **params):
        return {"text": "PASS", "model": model, "backend": "sentinel",
                "model_call_error": None}


def test_ac_scenario_010_author_test_bundle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author_calls.log"
    product_text = _build_fixture(repo_root, log_path)

    sentinel = _SentinelBackend()

    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel
    )

    assert log_path.is_file(), "author_test was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, lines
    record = json.loads(lines[0])

    assert record["model"] == "m"
    assert record["seed"] == 3
    assert record["repo_root"] is not None
    assert Path(record["repo_root"]).resolve() == repo_root.resolve()
    assert record["backend_is_none"] is False
    assert record["backend_id"] == id(sentinel)

    bundle = record["bundle"]
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] == "P-X"
    assert bundle["criterion_text"].strip() == GHERKIN.strip()
    assert product_text in bundle["requirement_text"]
    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface = bundle["interface"]
    i_bar_head = interface.find("## comp-bar")
    assert i_bar_head != -1, interface
    i_bar = interface.find("BAR_IFACE", i_bar_head)
    assert i_bar != -1, interface
    i_foo_head = interface.find("## comp-foo", i_bar)
    assert i_foo_head != -1, interface
    i_foo = interface.find("FOO_IFACE", i_foo_head)
    assert i_foo != -1, interface
    assert i_bar_head < i_bar < i_foo_head < i_foo