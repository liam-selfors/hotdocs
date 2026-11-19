# hotdocs-criterion: sha256:4a3e04c972b7c29a9e9262d670a6f7a3ad85f7b3165297507a26d03b84f6d7e2
import json
from pathlib import Path

import capability_scenario_verifier


CAP_ID = "P-X"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component_md(slug, title, realizes):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "realizes: [" + ", ".join(realizes) + "]\n"
        + "sealed: false\n"
        + "depends_on: []\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
    )


def _product_md():
    return (
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
        "Given a thing exists\n"
        "When the thing is used\n"
        "Then the thing works\n"
        "```\n"
    )


def _build_fixture(repo_root):
    author_log = repo_root.parent / "author_calls.log"
    run_log = repo_root.parent / "scenario_runs.log"

    # Capability
    _write(repo_root / "specs" / "product" / "x.md", _product_md())

    # Realizing component
    _write(repo_root / "specs" / "components" / "foo" / "component.md",
           _component_md("foo", "Foo", ["P-X"]))
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    _write(repo_root / "gen" / "foo" / "helper.py", "def helper():\n    return 0\n")

    # Non-realizing component
    _write(repo_root / "specs" / "components" / "bar" / "component.md",
           _component_md("bar", "Bar", []))
    _write(repo_root / "gen" / "bar" / "bar.py", "OTHER = 1\n")

    # Generated test content: logs each execution, then passes
    test_content = (
        "def test_x():\n"
        + "    with open(" + repr(str(run_log)) + ", 'a') as f:\n"
        + "        f.write('ran\\n')\n"
        + "    assert True\n"
    )

    author_src = (
        "LOG = " + repr(str(author_log)) + "\n"
        + "CONTENT = " + repr(test_content) + "\n"
        + "\n"
        + "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        + "    criterion_id = bundle['criterion_id']\n"
        + "    with open(LOG, 'a') as f:\n"
        + "        f.write(str(criterion_id) + '\\n')\n"
        + "    name = 'test_' + str(criterion_id).lower().replace('-', '_') + '.py'\n"
        + "    return {\n"
        + "        'component_id': 'capability:P-X',\n"
        + "        'criterion_id': criterion_id,\n"
        + "        'model': model,\n"
        + "        'seed': seed,\n"
        + "        'prompt_version': 'v1',\n"
        + "        'cache_hit': False,\n"
        + "        'file': {\n"
        + "            'path': 'verification/capabilities/P-X/generated-test/' + name,\n"
        + "            'content': CONTENT,\n"
        + "        },\n"
        + "        'model_call_error': None,\n"
        + "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", author_src)

    endpoint_src = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        + "    return {\n"
        + "        'text': 'pass',\n"
        + "        'model': model,\n"
        + "        'backend': 'fake',\n"
        + "        'model_call_error': None,\n"
        + "    }\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)

    return author_log, run_log


def _record_path(repo_root):
    return repo_root / "verification" / "capabilities" / CAP_ID / ".provenance.json"


def _record_hash(repo_root):
    data = json.loads(_record_path(repo_root).read_text())
    return data["content_hash"]


def _hit(repo_root):
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    return field(result, "hit")


def _run_count(run_log):
    if not run_log.is_file():
        return 0
    return len([ln for ln in run_log.read_text().splitlines() if ln.strip()])


def test_content_hash_tracks_realizing_code_and_capability_file(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    author_log, run_log = _build_fixture(repo_root)

    # Establish a committed record that is a hit.
    capability_scenario_verifier.run_capability_gates(
        CAP_ID, repo_root, model="fake-model", seed=0, llm_backend=None
    )
    assert _record_path(repo_root).is_file()
    original_hash = _record_hash(repo_root)
    assert isinstance(original_hash, str) and original_hash.startswith("sha256:")
    assert _hit(repo_root) is True

    # A change in a non-realizing component, or a __pycache__ file in a
    # realizing one, keeps the hit.
    (repo_root / "gen" / "bar" / "bar.py").write_text("OTHER = 2\n")
    pycache = repo_root / "gen" / "foo" / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "foo.cpython-311.pyc").write_bytes(b"\x00\x01\x02junk")
    assert _hit(repo_root) is True

    # Changing the capability's own specs/product file breaks the hit.
    product = repo_root / "specs" / "product" / "x.md"
    product_original = product.read_bytes()
    product.write_bytes(product_original.replace(b"Capability X\n\n###", b"Capability Y\n\n###", 1))
    assert product.read_bytes() != product_original
    assert _hit(repo_root) is False
    product.write_bytes(product_original)
    assert _hit(repo_root) is True

    # One byte changed in a realizing component's code, no spec change:
    # the hit is gone.
    code = repo_root / "gen" / "foo" / "foo.py"
    original_code = code.read_bytes()
    changed_code = original_code.replace(b"1", b"2", 1)
    assert len(changed_code) == len(original_code) and changed_code != original_code
    code.write_bytes(changed_code)
    assert _hit(repo_root) is False

    # run_capability_gates after that change re-runs the scenarios and
    # records a different content_hash.
    runs_before = _run_count(run_log)
    capability_scenario_verifier.run_capability_gates(
        CAP_ID, repo_root, model="fake-model", seed=0, llm_backend=None
    )
    runs_after = _run_count(run_log)
    assert runs_after > runs_before

    new_hash = _record_hash(repo_root)
    assert isinstance(new_hash, str) and new_hash.startswith("sha256:")
    assert new_hash != original_hash