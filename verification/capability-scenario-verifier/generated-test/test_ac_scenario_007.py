# hotdocs-criterion: sha256:c934cc4fe7a80951300fe0070a83ed0ceae4b93abea4bc015567d63c5655f6c1
import json
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component_md(slug, realizes, title):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: " + realizes + "\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "A fixture component.\n"
    )


PRODUCT_MD = (
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
    "Given a capability X\n"
    "When it is exercised\n"
    "Then it works\n"
    "```\n"
)


def _build_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    ctl = tmp_path / "ctl"
    ctl.mkdir()
    versions_file = ctl / "versions.json"
    author_log = ctl / "author.log"
    run_log = ctl / "run.log"

    # realizing component
    _write(repo / "specs" / "components" / "foo" / "component.md",
           _component_md("foo", "[P-X]", "Foo"))
    _write(repo / "gen" / "foo" / "foo.py", "VALUE = 1\n")

    # non-realizing component
    _write(repo / "specs" / "components" / "bar" / "component.md",
           _component_md("bar", "[]", "Bar"))
    _write(repo / "gen" / "bar" / "bar.py", "OTHER = 1\n")

    # capability
    _write(repo / "specs" / "product" / "x.md", PRODUCT_MD)

    # planted python adapter, versions controlled by a file outside repo_root
    adapter_src = (
        "import json\n"
        "import os\n"
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    path = " + repr(str(versions_file)) + "\n"
        "    versions = {}\n"
        "    if os.path.exists(path):\n"
        "        with open(path) as f:\n"
        "            versions = json.load(f)\n"
        "    return {'ok': True, 'reason': '', 'versions': versions,\n"
        "            'lockfile_sha256': None, 'interpreter': sys.executable}\n"
    )
    _write(repo / "gen" / "kind-python" / "kind_python.py", adapter_src)

    # generated test content: logs each execution, then passes
    test_content = (
        "def test_x():\n"
        "    with open(" + repr(str(run_log)) + ", 'a') as f:\n"
        "        f.write('ran\\n')\n"
        "    assert True\n"
    )
    rel_path = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"

    author_src = (
        "import os\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    cid = bundle['criterion_id'] if isinstance(bundle, dict) else getattr(bundle, 'criterion_id', None)\n"
        "    with open(" + repr(str(author_log)) + ", 'a') as f:\n"
        "        f.write(str(cid) + '\\n')\n"
        "    rel = " + repr(rel_path) + "\n"
        "    content = " + repr(test_content) + "\n"
        "    if repo_root is not None:\n"
        "        target = os.path.join(str(repo_root), rel)\n"
        "        os.makedirs(os.path.dirname(target), exist_ok=True)\n"
        "        with open(target, 'w') as f:\n"
        "            f.write(content)\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': cid,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': rel, 'content': content},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n"
    )
    _write(repo / "gen" / "test-author" / "test_author.py", author_src)

    endpoint_src = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {'text': 'PASS', 'model': model, 'backend': 'fake',\n"
        "            'model_call_error': None}\n"
    )
    _write(repo / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)

    return repo, versions_file, run_log


def _hit(repo):
    result = capability_scenario_verifier.check_capability_provenance("P-X", repo)
    return field(result, "hit")


def _record(repo):
    path = repo / "verification" / "capabilities" / "P-X" / ".provenance.json"
    return json.loads(path.read_text())


def _run_count(run_log):
    if not run_log.exists():
        return 0
    return len([ln for ln in run_log.read_text().splitlines() if ln.strip()])


def test_ac_scenario_007_content_hash_tracks_code_spec_and_environment(tmp_path):
    repo, versions_file, run_log = _build_repo(tmp_path)

    # Establish a committed record that is a hit.
    capability_scenario_verifier.run_capability_gates(
        "P-X", repo, "claude-sonnet-5", 0, None)
    record_before = _record(repo)
    hash_before = record_before["content_hash"]
    assert hash_before.startswith("sha256:")
    assert _hit(repo) is True

    # 1. One byte of a realizing component's code changes -> miss.
    foo_py = repo / "gen" / "foo" / "foo.py"
    original_foo = foo_py.read_bytes()
    foo_py.write_bytes(b"VALUE = 2\n")
    assert len(foo_py.read_bytes()) == len(original_foo)
    assert _hit(repo) is False
    foo_py.write_bytes(original_foo)
    assert _hit(repo) is True

    # 2. The capability's own specs/product file changes -> miss.
    product = repo / "specs" / "product" / "x.md"
    original_product = product.read_bytes()
    product.write_bytes(original_product + b"\n")
    assert _hit(repo) is False
    product.write_bytes(original_product)
    assert _hit(repo) is True

    # 3. The python adapter reports different versions -> miss.
    versions_file.write_text(json.dumps({"python": "3.14.7"}))
    assert _hit(repo) is False
    versions_file.unlink()
    assert _hit(repo) is True

    # 4. A non-realizing component's file changes -> still a hit.
    bar_py = repo / "gen" / "bar" / "bar.py"
    original_bar = bar_py.read_bytes()
    bar_py.write_bytes(b"OTHER = 2\n")
    assert _hit(repo) is True
    bar_py.write_bytes(original_bar)

    #    A __pycache__ file appears in a realizing component -> still a hit.
    pyc = repo / "gen" / "foo" / "__pycache__" / "foo.cpython-312.pyc"
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(b"\x00junk bytecode")
    assert _hit(repo) is True

    # 5. After the first change, run_capability_gates re-runs scenarios
    #    and records a different content_hash.
    runs_before = _run_count(run_log)
    foo_py.write_bytes(b"VALUE = 2\n")
    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo, "claude-sonnet-5", 0, None)
    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    assert "P-X" in report
    assert _run_count(run_log) > runs_before

    record_after = _record(repo)
    assert record_after["content_hash"] != hash_before
    assert record_after["content_hash"].startswith("sha256:")
    assert _hit(repo) is True