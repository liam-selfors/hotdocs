# hotdocs-criterion: sha256:efe9966cfb28f5464f0bba4ed9a50039c2b9feaa7e5d932e35bcd3ac15339a96
import hashlib
import json
import re
from pathlib import Path

import test_author


HEADER_PREFIX = "# hotdocs-criterion:"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(testing):
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "covers": "R-X-1",
        "criterion_text": "Given a\nWhen b\nThen c",
        "requirement_text": "R-X-1 MUST c",
        "interface": "I",
        "glossary": "G",
        "dependency_interfaces": {},
        "testing": testing,
    }


def expected_hex(bundle):
    payload = {
        k: bundle[k]
        for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('called\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock(file_content):
    def backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + file_content
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def run(tmp_path, monkeypatch, name, bundle, file_content):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-probe.log")
    write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_mock(file_content)
    )
    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    content = field(file, "content")
    path = field(file, "path")
    written = (repo_root / path).read_text(encoding="utf-8")
    return content, written


def test_header_is_computed_from_bundle(tmp_path, monkeypatch):
    bundle1 = make_bundle("T")
    content1, written1 = run(tmp_path, monkeypatch, "r1", bundle1, "import x")
    hex1 = expected_hex(bundle1)
    assert re.fullmatch(r"[0-9a-f]{64}", hex1)
    expected1 = "# hotdocs-criterion: sha256:" + hex1 + "\n" + "import x"
    assert content1 == expected1
    assert written1 == expected1

    # Same bundle but testing "T2": header hex differs.
    bundle2 = make_bundle("T2")
    content2, written2 = run(tmp_path, monkeypatch, "r2", bundle2, "import x")
    first2 = content2.split("\n", 1)[0]
    assert first2.startswith("# hotdocs-criterion: sha256:")
    hex2 = first2[len("# hotdocs-criterion: sha256:"):]
    assert hex2 != hex1
    assert hex2 == expected_hex(bundle2)

    # Model content already carrying a header line: replaced, never repeated.
    bundle3 = make_bundle("T")
    content3, written3 = run(
        tmp_path, monkeypatch, "r3", bundle3,
        "# hotdocs-criterion: sha256:0000\nimport x",
    )
    lines = content3.splitlines()
    header_lines = [ln for ln in lines if ln.startswith(HEADER_PREFIX)]
    assert len(header_lines) == 1
    assert lines[0].startswith(HEADER_PREFIX)
    assert lines[0] == "# hotdocs-criterion: sha256:" + expected_hex(bundle3)
    assert content3 == "# hotdocs-criterion: sha256:" + expected_hex(bundle3) + "\nimport x"
    assert written3 == content3