# hotdocs-criterion: sha256:d48fdf84e840bb8d0c728be9bc266186fac0daf2f4d60272ad9d06eed8379523
import re
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


TEST_CONTENT = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make():\n"
    "    assert widget_maker.make() == 1\n"
)


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen make is called\nThen it returns 1",
        "requirement_text": "R-WIDGET-MAKER-001 - make MUST return 1.",
        "interface": "make() -> int",
        "glossary": "",
        "dependency_interfaces": {},
    }


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    src = (
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(src, encoding="utf-8")


def _make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a") as f:
            f.write("call\n")
        n = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + n + "-----\n"
            + TEST_CONTENT
            + "\n-----END FILE " + n + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _cache_entries(repo_root):
    cache_dir = repo_root / ".hotdocs" / "cache"
    if not cache_dir.exists():
        return []
    return [p for p in cache_dir.rglob("*") if p.is_file()]


def test_cache_miss_result_is_written_to_cache_under_its_key(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_log = tmp_path / "probe.log"
    _write_probe_stand_in(repo_root, probe_log)

    # Given an empty cache
    assert _cache_entries(repo_root) == []

    first_log = tmp_path / "first_backend.log"
    first = test_author.author_test(
        _bundle(), "mock", 0, repo_root=repo_root, llm_backend=_make_backend(first_log)
    )

    assert field(first, "model_call_error") is None
    assert field(first, "cache_hit") is False
    assert first_log.read_text().count("call\n") >= 1
    first_file = field(first, "file")
    assert first_file is not None
    assert body(field(first_file, "content")) == TEST_CONTENT

    # Then cache-manager holds an entry afterward
    assert len(_cache_entries(repo_root)) >= 1

    # ...under the correct key: the same inputs now hit the cache and
    # return that same result without calling the model.
    second_log = tmp_path / "second_backend.log"
    second = test_author.author_test(
        _bundle(), "mock", 0, repo_root=repo_root, llm_backend=_make_backend(second_log)
    )

    assert field(second, "model_call_error") is None
    assert field(second, "cache_hit") is True
    assert not second_log.exists() or second_log.read_text() == ""
    second_file = field(second, "file")
    assert second_file is not None
    assert body(field(second_file, "content")) == TEST_CONTENT
    assert field(second_file, "content") == field(first_file, "content")
    assert field(second_file, "path") == field(first_file, "path")
    assert field(second, "criterion_id") == "AC-WIDGET-MAKER-001"
    assert field(second, "component_id") == "comp-widget-maker"