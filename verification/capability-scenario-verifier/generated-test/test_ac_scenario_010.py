# hotdocs-criterion: sha256:a0c8e008ac1cb070b8e01c41aec9c54c1326037bf25cc680c775350c84193d85
import json
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _SentinelBackend:
    marker = "SENTINEL-BACKEND-AC-SCENARIO-010"

    def __call__(self, prompt, model, **params):
        return {
            "text": "unused",
            "model": model,
            "backend": "sentinel",
            "model_call_error": None,
        }


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


GHERKIN = "Given the assembled system\nWhen it runs\nThen it passes"

BUNDLE_KEYS = [
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
    "module_names",
]


def _build_repo(repo_root, log_path):
    # python asset-kind adapter
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # components foo and bar realizing P-X
    for slug, iface in (("foo", "FOO_IFACE"), ("bar", "BAR_IFACE")):
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
            repo_root / "specs" / "components" / slug / "interface" / "library.md",
            iface,
        )
        _write(
            repo_root / "gen" / slug / (slug + ".py"),
            "def ping():\n    return 1\n",
        )

    # capability
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
        + GHERKIN
        + "\n```\n"
    )
    _write(repo_root / "specs" / "product" / "x.md", cap_text)

    # glossary
    _write(repo_root / "specs" / "glossary.md", "GLOSS")

    # fake test-author
    keys_src = repr(BUNDLE_KEYS)
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "import json\n"
        "\n"
        "GATE_VERSION = \"generated_test@3.0.0\"\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "KEYS = " + keys_src + "\n"
        "\n"
        "\n"
        "def _get(value, name):\n"
        "    if isinstance(value, dict):\n"
        "        return value.get(name)\n"
        "    return getattr(value, name, None)\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    record = {\n"
        "        \"bundle\": {k: _get(bundle, k) for k in KEYS},\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"repo_root\": None if repo_root is None else str(repo_root),\n"
        "        \"backend_marker\": getattr(llm_backend, \"marker\", None),\n"
        "        \"backend_id\": id(llm_backend),\n"
        "    }\n"
        "    with open(LOG_PATH, \"a\") as fh:\n"
        "        fh.write(json.dumps(record, default=str) + \"\\n\")\n"
        "    return {\n"
        "        \"component_id\": _get(bundle, \"component_id\"),\n"
        "        \"criterion_id\": _get(bundle, \"criterion_id\"),\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\n"
        "            \"path\": \"verification/capabilities/P-X/generated-test/test_cs_x_001.py\",\n"
        "            \"content\": \"def test_x():\\n    assert True\\n\",\n"
        "        },\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )

    # fake llm-endpoint
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"PASS\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )
    return cap_text


def test_run_capability_gates_builds_test_author_bundle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author_calls.log"
    cap_text = _build_repo(repo_root, log_path)

    sentinel = _SentinelBackend()
    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel
    )

    assert log_path.exists(), "author_test was never called"
    lines = [l for l in log_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 1, lines
    record = json.loads(lines[0])

    assert record["model"] == "m"
    assert record["seed"] == 3
    assert record["repo_root"] is not None
    assert Path(record["repo_root"]).resolve() == repo_root.resolve()
    assert record["backend_marker"] == _SentinelBackend.marker
    assert record["backend_id"] == id(sentinel)

    bundle = record["bundle"]
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] == "P-X"
    assert isinstance(bundle["criterion_text"], str)
    assert bundle["criterion_text"].strip() == GHERKIN.strip()
    assert isinstance(bundle["requirement_text"], str)
    assert cap_text.strip() in bundle["requirement_text"]
    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface = bundle["interface"]
    assert isinstance(interface, str)
    markers = ["## comp-bar", "BAR_IFACE", "## comp-foo", "FOO_IFACE"]
    positions = []
    start = 0
    for m in markers:
        idx = interface.find(m, start)
        assert idx >= 0, "missing or out of order: " + repr(m) + " in " + repr(interface)
        positions.append(idx)
        start = idx + len(m)
    assert positions == sorted(positions)