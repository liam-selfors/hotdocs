# hotdocs-criterion: sha256:05190eeaf7415be37f12563a5af3d8ee7ef3ca2f64852403cf16610ed20005de
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _plant_probe_stand_in(repo_root, log_path):
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('called\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_backend_never_receives_seed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    probe_log = tmp_path / "probe_calls.log"
    _plant_probe_stand_in(repo_root, probe_log)

    calls = []

    def spy_backend(*args, **kwargs):
        calls.append((args, dict(kwargs)))
        prompt = args[0] if args else kwargs.get("prompt", "")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_x():\n    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": args[1] if len(args) > 1 else kwargs.get("model"),
            "backend": "spy",
            "model_call_error": None,
        }

    result = test_author.author_test(
        _bundle(), "mock", 7, repo_root=repo_root, llm_backend=spy_backend
    )

    assert calls, "the spy backend was never called"
    for args, kwargs in calls:
        assert len(args) == 2, "expected exactly prompt and model positionally, got " + repr(args)
        assert isinstance(args[0], str)
        assert args[1] == "mock"
        assert "seed" not in kwargs, "seed was forwarded to the backend: " + repr(kwargs)
        assert "prompt" not in kwargs
        assert "model" not in kwargs

    assert field(result, "model_call_error") is None
    assert field(result, "seed") == 7