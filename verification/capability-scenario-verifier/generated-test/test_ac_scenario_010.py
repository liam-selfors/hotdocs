# hotdocs-criterion: sha256:1ff6fd20b16645c6f229b51856ed0d252a22af5706256b6029894a57a6a5fa0f
import json
import shutil
from pathlib import Path

import capability_scenario_verifier


GHERKIN = "Given a thing\nWhen it runs\nThen it works"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _SentinelBackend:
    def __call__(self, prompt, model, **params):
        return {
            "text": "PASS",
            "model": model,
            "backend": "sentinel",
            "model_call_error": None,
        }

    def __repr__(self):
        return "SENTINEL_BACKEND"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _live_repo_root():
    gen = next(
        p
        for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    return gen.parent


def _component(repo_root, slug, iface_text):
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug + "\n"
        + "status: draft\n"
        + "owners: [tester]\n"
        + "realizes: [P-X]\n"
        + "sealed: false\n"
        + "---\n\n"
        + "# comp-" + slug + "\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "interface" / "library.md",
        iface_text,
    )
    _write(
        repo_root / "gen" / slug / (slug.replace("-", "_") + ".py"),
        "VALUE = 1\n",
    )


def _build_fixture(repo_root, log_path):
    _component(repo_root, "foo", "FOO_IFACE")
    _component(repo_root, "bar", "BAR_IFACE")
    _write(repo_root / "specs" / "glossary.md", "GLOSS")

    capability_text = (
        "---\n"
        + "id: P-X\n"
        + "title: Capability X\n"
        + "status: draft\n"
        + "owners: [tester]\n"
        + "---\n\n"
        + "# P-X\n\n"
        + "### CS-X-001\n\n"
        + "Covers: P-X\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + GHERKIN + "\n"
        + "```\n"
    )
    _write(repo_root / "specs" / "product" / "x.md", capability_text)

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
    }
    author_src = (
        "import json\n"
        + "\n"
        + "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "RESULT = " + repr(result) + "\n"
        + "\n"
        + "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        + "    record = {\n"
        + "        'bundle': bundle,\n"
        + "        'model': model,\n"
        + "        'seed': seed,\n"
        + "        'repo_root': str(repo_root),\n"
        + "        'backend_id': id(llm_backend),\n"
        + "        'backend_repr': repr(llm_backend),\n"
        + "    }\n"
        + "    with open(LOG_PATH, 'a') as fh:\n"
        + "        fh.write(json.dumps(record, default=str) + '\\n')\n"
        + "    out = dict(RESULT)\n"
        + "    out['file'] = dict(RESULT['file'])\n"
        + "    return out\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", author_src)

    endpoint_src = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        + "    return {'text': 'PASS', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)

    compiler_src = _live_repo_root() / "pipeline" / "criterion-compiler"
    if compiler_src.is_dir():
        shutil.copytree(
            compiler_src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    return capability_text


def test_run_capability_gates_builds_author_test_bundle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author_calls.log"
    capability_text = _build_fixture(repo_root, log_path)

    sentinel = _SentinelBackend()
    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel
    )

    assert log_path.is_file(), "author_test was never called"
    lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1, lines
    call = json.loads(lines[0])

    assert call["model"] == "m"
    assert call["seed"] == 3
    assert Path(call["repo_root"]).resolve() == repo_root.resolve()
    assert call["backend_id"] == id(sentinel)
    assert call["backend_repr"] == "SENTINEL_BACKEND"

    bundle = call["bundle"]
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] == "P-X"
    assert bundle["criterion_text"].strip() == GHERKIN
    assert capability_text in bundle["requirement_text"]
    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface = bundle["interface"]
    i_bar_head = interface.find("## comp-bar")
    i_bar = interface.find("BAR_IFACE")
    i_foo_head = interface.find("## comp-foo")
    i_foo = interface.find("FOO_IFACE")
    assert i_bar_head != -1, interface
    assert i_bar != -1, interface
    assert i_foo_head != -1, interface
    assert i_foo != -1, interface
    assert i_bar_head < i_bar < i_foo_head < i_foo, interface