# hotdocs-criterion: sha256:5924e1e707684f9793bc69ccbbf0abc1c5e0a1f66d2b9270694bc6289c81e5d1
import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _bundle():
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('called\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_network_error_reported_as_model_call_error(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _plant_probe_stand_in(repo_root, probe_log)

    calls = {"n": 0}

    def failing_backend(prompt, model, **params):
        calls["n"] += 1
        raise ConnectionError("network unreachable")

    result = test_author.author_test(
        _bundle(), "mock", 0, repo_root=repo_root, llm_backend=failing_backend
    )

    assert calls["n"] >= 1

    model_call_error = field(result, "model_call_error")
    assert model_call_error is not None
    assert field(result, "file") is None
    assert field(result, "cache_hit") is False

    # Distinct from "the authored test ran but failed": no test was probed or written.
    assert not probe_log.exists() or probe_log.read_text(encoding="utf-8") == ""
    verification = repo_root / "verification"
    assert not verification.exists() or not any(
        p.is_file() for p in verification.rglob("*")
    )