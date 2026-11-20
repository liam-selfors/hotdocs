# hotdocs-criterion: sha256:b2d07bfd8b558cc920a5e0f5a82ea5882fd49121bce896c7284a3c367b91f826
import re

import test_author


LINE_RATIFIED = "- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`."
LINE_NO_YAML = "- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import dataclasses\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class ProbeReport:\n"
        "    ok: bool\n"
        "    findings: list\n"
        "    tests_run: int\n"
        "    tests_reached: int\n"
        "\n"
        "    def to_dict(self):\n"
        "        return dataclasses.asdict(self)\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport(ok=True, findings=[], tests_run=1, tests_reached=1)\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_prompt_holds_fixture_frontmatter_rules_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    test_file = (
        "import widget_maker\n"
        "\n"
        "\n"
        "def test_widget():\n"
        "    assert widget_maker.make() is not None\n"
    )

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = nonces[-1] if nonces else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_file
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen make() is called\nThen a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 — make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1

    lines = prompts[0].splitlines()
    assert LINE_RATIFIED in lines
    assert LINE_NO_YAML in lines