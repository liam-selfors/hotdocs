# hotdocs-criterion: sha256:1aefc1de1b59908431b83d87e02d212020a8d9cfe80f5ced6b203c7ff6d025b5
import hashlib
import json
from pathlib import Path

import capability_scenario_verifier


FAKE_TEST_AUTHOR = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    log = Path(repo_root) / 'calls.jsonl'\n"
    "    with open(log, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(bundle, default=str) + '\\n')\n"
    "    return {\n"
    "        'component_id': bundle.get('component_id'),\n"
    "        'criterion_id': bundle.get('criterion_id'),\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'model_call_error': None,\n"
    "        'file': {\n"
    "            'path': 'verification/capabilities/P-X/generated-test/test_cs_x_001.py',\n"
    "            'content': 'def test_x():\\n    assert True\\n',\n"
    "        },\n"
    "        'repair_attempts': 0,\n"
    "        'probe_findings': [],\n"
    "    }\n"
)

FAKE_LLM_ENDPOINT = (
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
)

TEST_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
BODY = "def test_x():\n    assert True\n"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(repo_root):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        "FOO_IFACE",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    _write(repo_root / "specs" / "glossary.md", "GLOSS")
    _write(
        repo_root / "specs" / "product" / "x.md",
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
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", FAKE_TEST_AUTHOR)
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT)
    assert not (repo_root / "verification" / "capabilities" / "P-X").exists()


def _bundles(repo_root):
    log = repo_root / "calls.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _hex_for(bundle):
    payload = {
        "criterion_text": bundle["criterion_text"],
        "requirement_text": bundle["requirement_text"],
        "interface": bundle["interface"],
        "glossary": bundle["glossary"],
        "testing": "",
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_steps(repo_root, header_for):
    _build(repo_root)
    capability_scenario_verifier.run_capability_gates("P-X", repo_root, "m")
    bundles = _bundles(repo_root)
    assert len(bundles) == 1
    header = header_for(bundles[0])
    _write(repo_root / TEST_PATH, header + "\n" + BODY)
    (repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json").unlink(missing_ok=True)
    capability_scenario_verifier.run_capability_gates("P-X", repo_root, "m")
    return _bundles(repo_root)


def test_current_committed_test_is_reused(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundles = _run_steps(
        repo_root, lambda b: "# hotdocs-criterion: sha256:" + _hex_for(b)
    )
    assert len(bundles) == 1


def test_stale_committed_test_is_reauthored(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundles = _run_steps(repo_root, lambda b: "# hotdocs-criterion: sha256:0000")
    assert len(bundles) == 2