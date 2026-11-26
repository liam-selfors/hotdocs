# hotdocs-criterion: sha256:445023b76a525d009c937c3d9b9459d0bfa1059d3668434b350a815632c1e9a6
import re

import test_author


LINE_ONE = (
    "the fake's own code appends one line per call to a log file at a path "
    "the test controls"
)
LINE_TWO = (
    "never with `str.format`, `%` or an f-string over text that holds "
    "braces or percent signs."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget When made Then it exists",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_block_r_author_024(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)

    prompts = []
    test_file = (
        "import widget_maker\n"
        "\n"
        "\n"
        "def test_make():\n"
        "    assert widget_maker.make_widget() is not None\n"
    )

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

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert result is not None
    assert len(prompts) >= 1
    first = prompts[0]
    assert LINE_ONE in first
    assert LINE_TWO in first