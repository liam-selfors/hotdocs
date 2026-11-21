# hotdocs-criterion: sha256:67c8a5b4c4d88de35036c295596e877f5145a449d072f70c8f1a978b52c35f9c
import json
import sys
from pathlib import Path

import capability_scenario_verifier


CAP = "P-X"
SCENARIO_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def adapter_source(versions):
    return (
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": "
        + repr(versions)
        + ", \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n"
    )


def component_md(slug, realizes):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [" + realizes + "]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
    )


def product_md(cap_id, short):
    return (
        "---\n"
        "id: " + cap_id + "\n"
        "title: Capability " + short + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Capability " + short + "\n"
        "\n"
        "### CS-" + short + "-001\n"
        "\n"
        "Covers: " + cap_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it passes\n"
        "```\n"
    )


def build_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.log"
    run_log = logs / "run.log"

    # Capabilities
    write(repo / "specs/product/x.md", product_md("P-X", "X"))
    write(repo / "specs/product/y.md", product_md("P-Y", "Y"))

    # Realizing component and a non-realizing one
    write(repo / "specs/components/foo/component.md", component_md("foo", "P-X"))
    write(repo / "gen/foo/foo.py", "VALUE = 1\n")
    write(repo / "specs/components/bar/component.md", component_md("bar", "P-Y"))
    write(repo / "gen/bar/bar.py", "OTHER = 1\n")

    # Planted python adapter
    write(repo / "gen/kind-python/kind_python.py", adapter_source({}))

    # The generated test records each execution
    content = (
        "def test_x():\n"
        "    with open(" + repr(str(run_log)) + ", \"a\") as f:\n"
        "        f.write(\"ran\\n\")\n"
        "    assert True\n"
    )

    # Fake test-author
    write(
        repo / "gen/test-author/test_author.py",
        "CONTENT = " + repr(content) + "\n"
        "LOG = " + repr(str(author_log)) + "\n"
        "PATH = " + repr(SCENARIO_PATH) + "\n"
        "GATE_VERSION = \"generated_test@3.0.0\"\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, \"a\") as f:\n"
        "        f.write(str(bundle[\"criterion_id\"]) + \"\\n\")\n"
        "    return {\n"
        "        \"component_id\": \"\",\n"
        "        \"criterion_id\": bundle[\"criterion_id\"],\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\"path\": PATH, \"content\": CONTENT},\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )

    # Fake llm-endpoint
    write(
        repo / "gen/llm-endpoint/llm_endpoint.py",
        "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"PASS\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )
    return repo, run_log


def record_path(repo):
    return repo / "verification" / "capabilities" / CAP / ".provenance.json"


def make_hit(tmp_path):
    repo, run_log = build_repo(tmp_path)
    capability_scenario_verifier.run_capability_gates(CAP, repo, model="fake-model", seed=0)
    assert record_path(repo).is_file()
    check = capability_scenario_verifier.check_capability_provenance(CAP, repo)
    assert field(check, "hit") is True
    return repo, run_log


def is_hit(repo):
    return field(capability_scenario_verifier.check_capability_provenance(CAP, repo), "hit")


def flip_code_byte(repo):
    path = repo / "gen/foo/foo.py"
    data = bytearray(path.read_bytes())
    idx = data.index(b"1")
    data[idx] = ord("2")
    path.write_bytes(bytes(data))


def test_code_byte_change_misses(tmp_path):
    repo, _ = make_hit(tmp_path)
    path = repo / "gen/foo/foo.py"
    original = path.read_bytes()
    flip_code_byte(repo)
    assert is_hit(repo) is False
    path.write_bytes(original)
    assert is_hit(repo) is True


def test_product_spec_change_misses(tmp_path):
    repo, _ = make_hit(tmp_path)
    path = repo / "specs/product/x.md"
    original = path.read_bytes()
    path.write_bytes(original + b"\n")
    assert is_hit(repo) is False
    path.write_bytes(original)
    assert is_hit(repo) is True


def test_python_versions_change_misses(tmp_path):
    sys.dont_write_bytecode = True
    repo, _ = make_hit(tmp_path)
    adapter = repo / "gen/kind-python/kind_python.py"
    adapter.write_text(adapter_source({"python": "3.14.7"}), encoding="utf-8")
    assert is_hit(repo) is False
    adapter.write_text(adapter_source({}), encoding="utf-8")
    assert is_hit(repo) is True


def test_unrelated_changes_still_hit(tmp_path):
    repo, _ = make_hit(tmp_path)
    (repo / "gen/bar/bar.py").write_text("OTHER = 2\n", encoding="utf-8")
    assert is_hit(repo) is True
    pyc = repo / "gen/foo/__pycache__/foo.cpython-314.pyc"
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(b"not really bytecode")
    assert is_hit(repo) is True


def test_rerun_after_code_change_writes_new_hash(tmp_path):
    repo, run_log = make_hit(tmp_path)
    before = json.loads(record_path(repo).read_text(encoding="utf-8"))["content_hash"]
    runs_before = run_log.read_text().count("ran") if run_log.exists() else 0

    flip_code_byte(repo)
    assert is_hit(repo) is False

    result = capability_scenario_verifier.run_capability_gates(CAP, repo, model="fake-model", seed=0)
    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert CAP in report

    runs_after = run_log.read_text().count("ran") if run_log.exists() else 0
    assert runs_after > runs_before

    after = json.loads(record_path(repo).read_text(encoding="utf-8"))["content_hash"]
    assert after.startswith("sha256:")
    assert after != before
    assert is_hit(repo) is True