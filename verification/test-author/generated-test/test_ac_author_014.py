# hotdocs-criterion: sha256:6e54306016dc7d9ccceee2425a45cda6a1d8834fed4d0b3ca5e77e70fb2152a2
import re

import test_author


EXPECTED_LINE = (
    "- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, "
    "`uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block "
    "style (`- a` lines), which the frontmatter reader does not read as a list."
)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_prompt_holds_block_r_author_014(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        n = nonces[-1] if nonces else "0" * 32
        body = "import widget_maker\n\n\ndef test_x():\n    widget_maker.make()\n"
        text = "-----BEGIN FILE " + n + "-----\n" + body + "\n-----END FILE " + n + "-----"
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
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - The maker MUST make widgets.",
        "interface": "make() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    test_author.author_test(bundle, "mock", repo_root=repo_root, llm_backend=mock_backend)

    assert prompts, "the mock model was never called"
    assert EXPECTED_LINE in prompts[0].splitlines()