# hotdocs-criterion: sha256:ada1422a95c667cca458abb8771d80fed5e33e9671b2d4c6ccb023364e796f0a
"""AC-SCENARIO-007: content_hash provenance covers realizing code, the
capability's own product spec and the provisioned environment versions,
and nothing else (R-SCENARIO-006)."""

import json
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


CAPABILITY_ID = "P-X"
MODEL = "fake-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _kind_python_source(versions):
    return (
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": " + repr(versions) + ", \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n"
    )


def _generated_test_content(run_log):
    return (
        "def test_x():\n"
        "    with open(" + repr(str(run_log)) + ", \"a\") as handle:\n"
        "        handle.write(\"ran\\n\")\n"
        "    assert True\n"
    )


def _test_author_source(author_log, content):
    return (
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(" + repr(str(author_log)) + ", \"a\") as handle:\n"
        "        handle.write(str(bundle[\"criterion_id\"]) + \"\\n\")\n"
        "    return {\n"
        "        \"component_id\": bundle.get(\"component_id\", \"\") if isinstance(bundle, dict) else \"\",\n"
        "        \"criterion_id\": bundle[\"criterion_id\"],\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\n"
        "            \"path\": \"verification/capabilities/P-X/generated-test/test_cs_x_001.py\",\n"
        "            \"content\": " + repr(content) + ",\n"
        "        },\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n"
    )


LLM_ENDPOINT_SOURCE = (
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\", \"model_call_error\": None}\n"
)


PRODUCT_TEXT = (
    "---\n"
    "id: P-X\n"
    "title: Capability X\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "---\n"
    "\n"
    "# P-X\n"
    "\n"
    "### CS-X-001\n"
    "\n"
    "Covers: P-X\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a repository\n"
    "When the capability runs\n"
    "Then it succeeds\n"
    "```\n"
)


def _component_md(slug, realizes):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: " + realizes + "\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# comp-" + slug + "\n"
    )


def _record_path(repo_root):
    return repo_root / "verification" / "capabilities" / CAPABILITY_ID / ".provenance.json"


def _read_record(repo_root):
    return json.loads(_record_path(repo_root).read_text())


def _lines(path):
    path = Path(path)
    if not path.is_file():
        return []
    return [line for line in path.read_text().splitlines() if line.strip()]


@pytest.fixture
def hit_repo(tmp_path):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.log"
    run_log = logs / "run.log"

    _write(repo_root / "gen" / "kind-python" / "kind_python.py", _kind_python_source({}))
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        _test_author_source(author_log, _generated_test_content(run_log)),
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", LLM_ENDPOINT_SOURCE)

    _write(repo_root / "specs" / "product" / "x.md", PRODUCT_TEXT)

    _write(repo_root / "specs" / "components" / "foo" / "component.md", _component_md("foo", "[P-X]"))
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")

    _write(repo_root / "specs" / "components" / "bar" / "component.md", _component_md("bar", "[]"))
    _write(repo_root / "gen" / "bar" / "bar.py", "OTHER = 1\n")

    first = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, model=MODEL, seed=0
    )
    assert field(first, "hit") is False
    assert _record_path(repo_root).is_file()
    record = _read_record(repo_root)
    report = record["capability_scenario_report"]
    assert report[CAPABILITY_ID]["overall"] == "pass", report

    check = capability_scenario_verifier.check_capability_provenance(CAPABILITY_ID, repo_root)
    assert field(check, "hit") is True

    return {
        "repo_root": repo_root,
        "author_log": author_log,
        "run_log": run_log,
        "record": record,
    }


def test_realizing_code_byte_change_is_a_miss(hit_repo):
    repo_root = hit_repo["repo_root"]
    code = repo_root / "gen" / "foo" / "foo.py"
    data = bytearray(code.read_bytes())
    index = data.index(b"1")
    data[index] = ord("2")
    code.write_bytes(bytes(data))

    result = capability_scenario_verifier.check_capability_provenance(CAPABILITY_ID, repo_root)
    assert field(result, "hit") is False
    assert field(result, "capability_scenario_report") is None


def test_product_spec_change_is_a_miss(hit_repo):
    repo_root = hit_repo["repo_root"]
    product = repo_root / "specs" / "product" / "x.md"
    product.write_text(product.read_text() + "\n")

    result = capability_scenario_verifier.check_capability_provenance(CAPABILITY_ID, repo_root)
    assert field(result, "hit") is False


def test_provisioned_python_versions_change_is_a_miss(hit_repo):
    repo_root = hit_repo["repo_root"]
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        _kind_python_source({"python": "3.14.7"}),
    )

    result = capability_scenario_verifier.check_capability_provenance(CAPABILITY_ID, repo_root)
    assert field(result, "hit") is False


def test_non_realizing_change_and_pycache_still_hit(hit_repo):
    repo_root = hit_repo["repo_root"]
    _write(repo_root / "gen" / "bar" / "bar.py", "OTHER = 2\n")
    pycache = repo_root / "gen" / "foo" / "__pycache__" / "foo.cpython-314.pyc"
    pycache.parent.mkdir(parents=True, exist_ok=True)
    pycache.write_bytes(b"\x00\x01fake bytecode")

    result = capability_scenario_verifier.check_capability_provenance(CAPABILITY_ID, repo_root)
    assert field(result, "hit") is True
    assert field(result, "capability_scenario_report") == hit_repo["record"]["capability_scenario_report"]


def test_run_after_code_change_reruns_and_records_new_hash(hit_repo):
    repo_root = hit_repo["repo_root"]
    old_hash = hit_repo["record"]["content_hash"]
    runs_before = len(_lines(hit_repo["run_log"]))
    authored_before = len(_lines(hit_repo["author_log"]))
    assert runs_before + authored_before >= 1

    code = repo_root / "gen" / "foo" / "foo.py"
    data = bytearray(code.read_bytes())
    index = data.index(b"1")
    data[index] = ord("2")
    code.write_bytes(bytes(data))

    result = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, model=MODEL, seed=0
    )
    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    assert CAPABILITY_ID in report

    runs_after = len(_lines(hit_repo["run_log"]))
    authored_after = len(_lines(hit_repo["author_log"]))
    assert runs_after > runs_before or authored_after > authored_before

    new_record = _read_record(repo_root)
    assert new_record["content_hash"].startswith("sha256:")
    assert new_record["content_hash"] != old_hash