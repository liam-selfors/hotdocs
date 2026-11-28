# hotdocs-criterion: sha256:5f9178397d8a65834777e6a7a6c32cf8b265a40edfed37144f968006b8198216
import re

import test_author


EXPECTED_LINE = (
    "- Only a criterion that needs `realizes`-driven behavior has the fixture "
    "supply a resolvable `P-<id>`."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _make_mock_backend(prompts):
    test_file = "def test_placeholder():\n    assert True\n"

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = nonces[-1]
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

    return backend


def test_prompt_holds_r_author_013_realizes_line(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - The maker MUST make a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    prompts = []
    backend = _make_mock_backend(prompts)

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=backend
    )

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1

    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()