# hotdocs-criterion: sha256:9332fc223da4e57c33023454df516330845b06953c888e1dd974088ccbf673bf
import re

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

CACHED_TEST = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_cached():\n"
    "    assert widget_maker.make() is not None\n"
)

FRESH_TEST = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_fresh_should_never_appear():\n"
    "    assert widget_maker.other() is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given a widget maker\n"
            "When make is called\n"
            "Then a widget is returned"
        ),
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


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
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock(test_source, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_source
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def read_lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_cache_hit_returns_cached_result_without_calling_model(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    write_probe_stand_in(repo_root, logs / "probe.log")

    # Pre-populate the cache for this criterion content hash and model.
    populate_log = logs / "populate_model.log"
    first = test_author.author_test(
        make_bundle(),
        "mock",
        0,
        repo_root=repo_root,
        llm_backend=make_mock(CACHED_TEST, populate_log),
    )
    assert field(first, "model_call_error") is None
    assert field(first, "cache_hit") is False
    assert len(read_lines(populate_log)) >= 1
    first_file = field(first, "file")
    assert first_file is not None
    assert body(first_file["content"]) == CACHED_TEST

    cache_dir = repo_root / ".hotdocs" / "cache"
    assert cache_dir.exists()
    assert any(p.is_file() for p in cache_dir.rglob("*"))

    # Matching inputs: the mock model must never be called.
    second_log = logs / "second_model.log"
    second = test_author.author_test(
        make_bundle(),
        "mock",
        0,
        repo_root=repo_root,
        llm_backend=make_mock(FRESH_TEST, second_log),
    )

    assert read_lines(second_log) == []
    assert field(second, "cache_hit") is True
    assert field(second, "model_call_error") is None
    assert field(second, "repair_attempts") == 0
    assert field(second, "probe_findings") == []
    assert field(second, "component_id") == "comp-widget-maker"
    assert field(second, "criterion_id") == "AC-WIDGET-MAKER-001"
    assert field(second, "model") == "mock"

    second_file = field(second, "file")
    assert second_file is not None
    assert second_file["path"] == first_file["path"]
    assert body(second_file["content"]) == CACHED_TEST
    assert second_file["content"] == first_file["content"]