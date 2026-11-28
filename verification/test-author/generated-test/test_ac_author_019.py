# hotdocs-criterion: sha256:ef4bad3280b41cde6d0bee77d51eab3d90aefd6ed720ce4dc4e3f2effcbb6827
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PROBE_STANDIN = (
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
    "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
    "    return _Report()\n"
)


def _make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - A widget MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_backend_receives_only_prompt_and_model_and_no_seed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(PROBE_STANDIN, encoding="utf-8")

    calls = []

    def spy_backend(*args, **kwargs):
        calls.append((args, dict(kwargs)))
        prompt = args[0] if args else kwargs.get("prompt", "")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_ok():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": "mock",
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        _make_bundle(), "mock", 7, repo_root=repo_root, llm_backend=spy_backend
    )

    assert calls, "the spy backend was never called"
    for args, kwargs in calls:
        assert len(args) == 2, "expected exactly prompt and model positionally, got %d" % len(args)
        assert isinstance(args[0], str)
        assert args[1] == "mock"
        assert "seed" not in kwargs, "seed was forwarded to the backend: " + repr(kwargs)
        assert "prompt" not in kwargs
        assert "model" not in kwargs

    assert field(result, "model_call_error") is None
    assert field(result, "seed") == 7