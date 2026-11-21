# hotdocs-criterion: sha256:c04e02081c04458dcbf94577d76f1b1ce2e8a2ca58bbaa7b4c67f1a424e1049c
import json
import sys
from pathlib import Path

import capability_scenario_verifier


GHERKIN = "Given a thing is ready\nWhen the thing runs\nThen the thing passes\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def plant_component(repo_root, slug):
    write(
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
    write(
        repo_root / "gen" / slug / (slug + ".py"),
        "def ping():\n    return " + repr(slug) + "\n",
    )


def build_fixture(repo_root, log_path):
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    plant_component(repo_root, "foo")
    plant_component(repo_root, "bar")
    write(repo_root / "specs" / "components" / "foo" / "interface" / "library.md", "FOO_IFACE\n")
    write(repo_root / "specs" / "components" / "bar" / "interface" / "library.md", "BAR_IFACE\n")
    write(repo_root / "specs" / "glossary.md", "GLOSS")

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
        "CAPABILITY_X_BODY\n"
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
    write(repo_root / "specs" / "product" / "x.md", capability_text)

    result = {
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
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "RESULT = " + repr(result) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    record = {\n"
        "        \"bundle\": dict(bundle),\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"repo_root\": None if repo_root is None else str(repo_root),\n"
        "        \"backend_id\": id(llm_backend),\n"
        "    }\n"
        "    with open(LOG, \"a\") as handle:\n"
        "        handle.write(json.dumps(record, default=str) + \"\\n\")\n"
        "    return dict(RESULT)\n",
    )
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"PASS\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )
    return capability_text


def test_run_capability_gates_builds_author_test_bundle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author_calls.log"
    capability_text = build_fixture(repo_root, log_path)

    sentinel = object()
    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel
    )

    assert log_path.is_file(), "author_test was never called"
    lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    call = json.loads(lines[0])

    assert call["model"] == "m"
    assert call["seed"] == 3
    assert call["repo_root"] is not None
    assert Path(call["repo_root"]).resolve() == repo_root.resolve()
    assert call["backend_id"] == id(sentinel)

    bundle = call["bundle"]
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] in ("P-X", ["P-X"])
    assert bundle["criterion_text"].strip() == GHERKIN.strip()
    assert capability_text.strip() in bundle["requirement_text"]
    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface = bundle["interface"]
    positions = []
    start = 0
    for marker in ("## comp-bar", "BAR_IFACE", "## comp-foo", "FOO_IFACE"):
        index = interface.find(marker, start)
        assert index >= 0, "missing or out of order: " + repr(marker)
        positions.append(index)
        start = index + len(marker)
    assert positions == sorted(positions)