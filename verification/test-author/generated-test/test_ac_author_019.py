# hotdocs-criterion: sha256:eceac991c8e244941a723edc93b5c62e3637d3f601d9e579101622bfd723b6cf
import re

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"


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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget When made Then it exists",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_backend_receives_only_prompt_and_model_and_no_seed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    calls = []

    def spy_backend(*args, **kwargs):
        calls.append({"args": args, "kwargs": dict(kwargs)})
        prompt = args[0] if args else kwargs.get("prompt", "")
        model = args[1] if len(args) > 1 else kwargs.get("model", "mock")
        matches = re.findall(NONCE_RE, prompt)
        nonce = matches[-1] if matches else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_x():\n    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "spy",
            "model_call_error": None,
        }

    result = test_author.author_test(
        _bundle(), "mock", 7, repo_root=repo_root, llm_backend=spy_backend
    )

    assert result is not None
    assert len(calls) >= 1, "the spy backend was never called"

    for call in calls:
        args = call["args"]
        kwargs = call["kwargs"]
        assert len(args) == 2, (
            "backend must receive exactly prompt and model positionally, got "
            + repr(args)
        )
        assert isinstance(args[0], str)
        assert args[1] == "mock"
        assert "prompt" not in kwargs
        assert "model" not in kwargs
        assert "seed" not in kwargs, (
            "seed must never be forwarded to the backend, got kwargs "
            + repr(kwargs)
        )