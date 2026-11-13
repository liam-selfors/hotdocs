import json
import shutil
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


CAP_ID = "P-X"
MODEL = "claude-sonnet-5"
RECORD_REL = Path("verification") / "capabilities" / CAP_ID / ".provenance.json"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


FAKE_TEST_AUTHOR = r'''
import json
from pathlib import Path


def _logs_dir(repo_root):
    if repo_root is not None:
        return Path(repo_root).resolve().parent / "logs"
    return Path(__file__).resolve().parents[3] / "logs"


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    criterion_id = _get(bundle, "criterion_id")
    _get(bundle, "criterion_text")
    logs = _logs_dir(repo_root)
    logs.mkdir(parents=True, exist_ok=True)
    with open(logs / "author_calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"criterion_id": criterion_id, "model": model, "seed": seed}) + "\n")
    exec_log = logs / "executions.log"
    stem = "test_" + str(criterion_id).lower().replace("-", "_")
    rel = "verification/capabilities/P-X/generated-test/" + stem + ".py"
    content = (
        "def test_x():\n"
        "    with open(" + repr(str(exec_log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('ran\\n')\n"
        "    assert True\n"
    )
    if repo_root is not None:
        target = Path(repo_root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return {
        "component_id": "P-X",
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": rel, "content": content},
        "model_call_error": None,
    }
'''


FAKE_LLM_ENDPOINT = r'''
def complete(prompt, model, *, backend=None, **params):
    return {
        "text": '{"result": "pass", "rationale": "fake judge"}',
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }
'''


def _fake_backend(prompt, model, **params):
    return {
        "text": '{"result": "pass", "rationale": "fake judge"}',
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }


def _component_md(slug, realizes):
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [tester]\n"
        "depends_on: []\n"
        f"realizes: [{realizes}]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        f"# {slug}\n"
        "\n"
        "A synthetic fixture component.\n"
    )


def _capability_md(cap_id, suffix):
    return (
        "---\n"
        f"id: {cap_id}\n"
        f"title: Capability {suffix}\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        f"# {cap_id}\n"
        "\n"
        f"### CS-{suffix}-001\n"
        "\n"
        f"Covers: {cap_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a configured system\n"
        "When the capability is exercised\n"
        "Then it behaves as described\n"
        "```\n"
    )


def _build_repo(root):
    (root / "specs" / "product").mkdir(parents=True)
    (root / "specs" / "product" / "capability-x.md").write_text(_capability_md("P-X", "X"), encoding="utf-8")
    (root / "specs" / "product" / "capability-y.md").write_text(_capability_md("P-Y", "Y"), encoding="utf-8")

    for slug, realizes in (("foo", "P-X"), ("bar", "P-Y")):
        cdir = root / "specs" / "components" / slug
        cdir.mkdir(parents=True)
        (cdir / "component.md").write_text(_component_md(slug, realizes), encoding="utf-8")
        gdir = root / "gen" / slug
        gdir.mkdir(parents=True)
        (gdir / f"{slug}.py").write_text('VALUE = "a"\n', encoding="utf-8")

    ta = root / "gen" / "test-author"
    ta.mkdir(parents=True)
    (ta / "test_author.py").write_text(FAKE_TEST_AUTHOR, encoding="utf-8")
    le = root / "gen" / "llm-endpoint"
    le.mkdir(parents=True)
    (le / "llm_endpoint.py").write_text(FAKE_LLM_ENDPOINT, encoding="utf-8")

    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__"),
            )


def _snapshot(directory):
    return {
        str(p.relative_to(directory)): p.read_bytes()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def _count_lines(path):
    if not path.is_file():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def _flip_one_byte(path):
    data = bytearray(path.read_bytes())
    idx = data.index(b"a"[0])
    data[idx] = b"b"[0]
    path.write_bytes(bytes(data))


@pytest.fixture
def hit_repo(tmp_path, monkeypatch):
    for name in ("test_author", "llm_endpoint"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (tmp_path / "logs").mkdir()
    _build_repo(repo_root)

    first = capability_scenario_verifier.run_capability_gates(
        CAP_ID, repo_root, model=MODEL, seed=0, llm_backend=_fake_backend
    )
    assert field(first, "hit") is False
    record_path = repo_root / RECORD_REL
    assert record_path.is_file(), "run_capability_gates did not write the committed record"

    check = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(check, "hit") is True, "precondition: committed record must be a hit"
    return repo_root


def test_one_byte_change_in_realizing_code_is_a_miss(hit_repo):
    repo_root = hit_repo
    specs_before = _snapshot(repo_root / "specs")

    _flip_one_byte(repo_root / "gen" / "foo" / "foo.py")

    assert _snapshot(repo_root / "specs") == specs_before, "no spec file may change"
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False


def test_capability_product_file_change_is_a_miss(hit_repo):
    repo_root = hit_repo
    product = repo_root / "specs" / "product" / "capability-x.md"
    product.write_text(product.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is False


def test_unrelated_component_change_and_pycache_keep_hit(hit_repo):
    repo_root = hit_repo

    _flip_one_byte(repo_root / "gen" / "bar" / "bar.py")
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is True

    pycache = repo_root / "gen" / "foo" / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "foo.cpython-312.pyc").write_bytes(b"\x00\x01fake-bytecode\x02")
    result = capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root)
    assert field(result, "hit") is True


def test_run_after_change_reruns_and_rewrites_content_hash(hit_repo):
    repo_root = hit_repo
    logs = repo_root.parent / "logs"
    record_path = repo_root / RECORD_REL

    before_record = json.loads(record_path.read_text(encoding="utf-8"))
    before_hash = before_record["content_hash"]
    assert isinstance(before_hash, str) and before_hash.startswith("sha256:")

    author_calls_before = _count_lines(logs / "author_calls.jsonl")
    executions_before = _count_lines(logs / "executions.log")

    _flip_one_byte(repo_root / "gen" / "foo" / "foo.py")
    assert field(
        capability_scenario_verifier.check_capability_provenance(CAP_ID, repo_root), "hit"
    ) is False

    result = capability_scenario_verifier.run_capability_gates(
        CAP_ID, repo_root, model=MODEL, seed=0, llm_backend=_fake_backend
    )

    assert field(result, "hit") is False
    report = field(result, "capability_scenario_report")
    assert report is not None
    entry = report[CAP_ID] if isinstance(report, dict) else getattr(report, CAP_ID)
    scenario_ids = [field(s, "id") for s in field(entry, "scenarios")]
    assert "CS-X-001" in scenario_ids

    author_calls_after = _count_lines(logs / "author_calls.jsonl")
    executions_after = _count_lines(logs / "executions.log")
    assert (
        executions_after > executions_before or author_calls_after > author_calls_before
    ), "scenarios were not re-run after the change"

    after_record = json.loads(record_path.read_text(encoding="utf-8"))
    after_hash = after_record["content_hash"]
    assert isinstance(after_hash, str) and after_hash.startswith("sha256:")
    assert after_hash != before_hash