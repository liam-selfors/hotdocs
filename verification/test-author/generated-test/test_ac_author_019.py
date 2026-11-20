# hotdocs-criterion: sha256:3b9d01bf9be4e6176129b95a36a0565039174a553ed2d8f472697f22d63634d3
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import dataclasses\n"
        "\n"
        "GATE_VERSION = " + repr("test-probe@1.3.0") + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
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
        "        return {\n"
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": list(self.findings),\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG_PATH, " + repr("a") + ") as fh:\n"
        "        fh.write(" + repr("probe\n") + ")\n"
        "    return ProbeReport(ok=True, findings=[], tests_run=1, tests_reached=1)\n"
    )
    (probe_dir / "test_probe.py").write_text(source)


def test_backend_never_receives_seed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    calls = []
    test_file = "def test_placeholder():\n    assert True\n"

    def spy_backend(*args, **kwargs):
        calls.append((args, dict(kwargs)))
        prompt = args[0] if args else kwargs.get("prompt", "")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_file
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": "mock",
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - a widget MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", 7, repo_root=repo_root, llm_backend=spy_backend
    )

    assert field(result, "model_call_error") is None
    assert len(calls) >= 1

    for args, kwargs in calls:
        assert len(args) == 2, "backend got positional args beyond prompt and model: %r" % (args,)
        assert isinstance(args[0], str)
        assert args[1] == "mock"
        assert "seed" not in kwargs, "seed was forwarded to the backend: %r" % (kwargs,)