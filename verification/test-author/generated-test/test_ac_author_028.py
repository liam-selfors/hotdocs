# hotdocs-criterion: sha256:9efd72251a5c39a52f640c3ba9fa4aaeccfe026f95d1e0d3c95fc1e7d2a3056a
import hashlib
import json
import re
from pathlib import Path

import test_author


CRITERION_TEXT = "Given a\nWhen b\nThen c"
REQUIREMENT_TEXT = "R-X-1 MUST c"
INTERFACE = "I"
GLOSSARY = "G"
HEADER_PREFIX = "# hotdocs-criterion:"
EXPECTED_PATH = "verification/foo/generated-test/test_ac_foo_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(testing):
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE,
        "glossary": GLOSSARY,
        "dependency_interfaces": {},
        "testing": testing,
    }


def expected_hex(testing):
    payload = {
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE,
        "glossary": GLOSSARY,
        "testing": testing,
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plant_probe(repo_root, log_path):
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
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock(content):
    def backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + content
            + "\n-----END FILE " + nonce + "-----"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def run(repo_root, monkeypatch, testing, content):
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(repo_root)
    log_path = repo_root.parent / (repo_root.name + "-probe.log")
    plant_probe(repo_root, log_path)
    result = test_author.author_test(
        make_bundle(testing), "mock", repo_root=repo_root, llm_backend=make_mock(content)
    )
    assert field(result, "model_call_error") is None
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("probe\n") >= 1
    file = field(result, "file")
    assert file is not None
    return file


def test_header_is_computed_from_bundle_and_prefixes_model_content(tmp_path, monkeypatch):
    repo_root = tmp_path / "s1"
    file = run(repo_root, monkeypatch, "T", "import x")
    expected = HEADER_PREFIX + " sha256:" + expected_hex("T") + "\n" + "import x"
    assert file["content"] == expected
    assert file["path"] == EXPECTED_PATH
    written = (repo_root / file["path"]).read_bytes().decode("utf-8")
    assert written == expected


def test_header_hex_changes_with_testing(tmp_path, monkeypatch):
    first = run(tmp_path / "s1", monkeypatch, "T", "import x")
    second = run(tmp_path / "s2", monkeypatch, "T2", "import x")
    first_line = first["content"].split("\n", 1)[0]
    second_line = second["content"].split("\n", 1)[0]
    assert first_line.startswith(HEADER_PREFIX + " sha256:")
    assert second_line.startswith(HEADER_PREFIX + " sha256:")
    first_hex = first_line[len(HEADER_PREFIX + " sha256:"):]
    second_hex = second_line[len(HEADER_PREFIX + " sha256:"):]
    assert first_hex != second_hex
    assert second_hex == expected_hex("T2")


def test_model_supplied_header_is_replaced_not_repeated(tmp_path, monkeypatch):
    repo_root = tmp_path / "s3"
    file = run(
        repo_root, monkeypatch, "T", "# hotdocs-criterion: sha256:0000\nimport x"
    )
    content = file["content"]
    lines = content.split("\n")
    header_lines = [i for i, line in enumerate(lines) if line.startswith(HEADER_PREFIX)]
    assert header_lines == [0]
    assert lines[0] == HEADER_PREFIX + " sha256:" + expected_hex("T")
    assert content == lines[0] + "\n" + "import x"
    written = (repo_root / file["path"]).read_bytes().decode("utf-8")
    assert written == content