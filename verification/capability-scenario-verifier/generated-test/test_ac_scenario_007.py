# hotdocs-criterion: sha256:4a3e04c972b7c29a9e9262d670a6f7a3ad85f7b3165297507a26d03b84f6d7e2
import json
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


CAPABILITY_ID = "P-X"
MODEL = "fake-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _live_repo_root():
    gen = next(
        p
        for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    return gen.parent


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PRODUCT_MD = (
    "---\n"
    "id: P-X\n"
    "title: X capability\n"
    "status: draft\n"
    "owners: [tester]\n"
    "---\n"
    "\n"
    "# P-X\n"
    "\n"
    "The X capability.\n"
    "\n"
    "### CS-X-001\n"
    "\n"
    "Covers: P-X\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a thing exists\n"
    "When it runs\n"
    "Then it works\n"
    "```\n"
)


def _component_md(slug, realizes):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: " + realizes + "\n"
        "depends_on: []\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
    )


def _fake_test_author_source(log_path):
    return (
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "CONTENT = " + repr("def test_x():\n    assert True\n") + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    criterion_id = bundle['criterion_id']\n"
        "    _text = bundle['criterion_text']\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('author_test ' + str(criterion_id) + '\\n')\n"
        "    rel = 'verification/capabilities/P-X/generated-test/test_' + "
        "str(criterion_id).lower().replace('-', '_') + '.py'\n"
        "    if repo_root is not None:\n"
        "        target = Path(repo_root) / rel\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        target.write_text(CONTENT, encoding='utf-8')\n"
        "    return {\n"
        "        'component_id': 'P-X',\n"
        "        'criterion_id': criterion_id,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': rel, 'content': CONTENT},\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )


def _fake_llm_endpoint_source(log_path):
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    return {\n"
        "        'text': 'PASS',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

    _write(repo_root / "specs" / "product" / "x.md", PRODUCT_MD)

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        _component_md("foo", "[P-X]"),
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")

    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        _component_md("bar", "[]"),
    )
    _write(repo_root / "gen" / "bar" / "bar.py", "OTHER = 1\n")

    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        _fake_test_author_source(log_path),
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        _fake_llm_endpoint_source(log_path),
    )

    src = _live_repo_root() / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    return repo_root, log_path


def _record_path(repo_root):
    return (
        repo_root / "verification" / "capabilities" / CAPABILITY_ID / ".provenance.json"
    )


def _read_record(repo_root):
    return json.loads(_record_path(repo_root).read_text(encoding="utf-8"))


@pytest.fixture
def hit_repo(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, model=MODEL, seed=0, llm_backend=None
    )
    assert _record_path(repo_root).is_file()
    check = capability_scenario_verifier.check_capability_provenance(
        CAPABILITY_ID, repo_root
    )
    assert field(check, "hit") is True
    return repo_root, log_path


def _change_one_byte(path):
    data = bytearray(path.read_bytes())
    idx = data.index(ord("1"))
    data[idx] = ord("2")
    path.write_bytes(bytes(data))


def test_realizing_component_code_change_is_miss(hit_repo):
    repo_root, _ = hit_repo
    _change_one_byte(repo_root / "gen" / "foo" / "foo.py")
    check = capability_scenario_verifier.check_capability_provenance(
        CAPABILITY_ID, repo_root
    )
    assert field(check, "hit") is False


def test_capability_product_spec_change_is_miss(hit_repo):
    repo_root, _ = hit_repo
    product = repo_root / "specs" / "product" / "x.md"
    text = product.read_text(encoding="utf-8")
    product.write_text(
        text.replace("The X capability.", "The X capability!"), encoding="utf-8"
    )
    check = capability_scenario_verifier.check_capability_provenance(
        CAPABILITY_ID, repo_root
    )
    assert field(check, "hit") is False


def test_non_realizing_component_change_still_hit(hit_repo):
    repo_root, _ = hit_repo
    _change_one_byte(repo_root / "gen" / "bar" / "bar.py")
    check = capability_scenario_verifier.check_capability_provenance(
        CAPABILITY_ID, repo_root
    )
    assert field(check, "hit") is True


def test_pycache_in_realizing_component_still_hit(hit_repo):
    repo_root, _ = hit_repo
    pyc = repo_root / "gen" / "foo" / "__pycache__" / "foo.cpython-311.pyc"
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(b"\x00\x01fake-bytecode")
    check = capability_scenario_verifier.check_capability_provenance(
        CAPABILITY_ID, repo_root
    )
    assert field(check, "hit") is True


def test_run_after_code_change_reruns_and_updates_hash(hit_repo):
    repo_root, _ = hit_repo
    before = _read_record(repo_root)
    before_hash = before["content_hash"]
    assert isinstance(before_hash, str) and before_hash.startswith("sha256:")

    _change_one_byte(repo_root / "gen" / "foo" / "foo.py")

    result = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, model=MODEL, seed=0, llm_backend=None
    )

    # A fresh run reports hit false with the fresh report (nothing reused).
    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    entry = report[CAPABILITY_ID] if isinstance(report, dict) else getattr(report, CAPABILITY_ID)
    scenarios = field(entry, "scenarios")
    ids = [field(s, "id") for s in scenarios]
    assert "CS-X-001" in ids

    after = _read_record(repo_root)
    assert after["capability_id"] == CAPABILITY_ID
    assert after["content_hash"].startswith("sha256:")
    assert after["content_hash"] != before_hash

    # The new record now matches the tree again.
    check = capability_scenario_verifier.check_capability_provenance(
        CAPABILITY_ID, repo_root
    )
    assert field(check, "hit") is True