# hotdocs-criterion: sha256:d28237078c2d5e16db48fc15e40628c1823f5d28c1e6b1575f37b4df1a0ee5b3
import hashlib
import json
import re
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HEADER_PREFIX = "# hotdocs-criterion:"


def make_bundle(testing="T"):
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-003",
        "covers": "R-FOO-003",
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


def plant_probe(repo_root, log_path):
    probe_dir = Path(repo_root) / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        "    with open(LOG_PATH, " + repr("a") + ", encoding=" + repr("utf-8") + ") as f:\n"
        "        f.write(repr(test_source) + " + repr("\n") + ")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(file_content):
    def backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + file_content
            + "\n-----END FILE " + nonce + "-----"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def run(tmp_path, monkeypatch, name, bundle, model_content):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-probe.log")
    plant_probe(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_backend(model_content)
    )
    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    return repo_root, file


def test_header_computed_from_bundle(tmp_path, monkeypatch):
    bundle1 = make_bundle("T")
    repo1, file1 = run(tmp_path, monkeypatch, "r1", bundle1, "import x")
    hex1 = expected_hex(bundle1)
    assert re.fullmatch(r"[0-9a-f]{64}", hex1)
    expected1 = "# hotdocs-criterion: sha256:" + hex1 + "\n" + "import x"
    assert field(file1, "content") == expected1
    written1 = (repo1 / field(file1, "path")).read_text(encoding="utf-8")
    assert written1 == expected1

    bundle2 = make_bundle("T2")
    repo2, file2 = run(tmp_path, monkeypatch, "r2", bundle2, "import x")
    first_line2 = field(file2, "content").partition("\n")[0]
    assert first_line2.startswith("# hotdocs-criterion: sha256:")
    hex2 = first_line2[len("# hotdocs-criterion: sha256:"):]
    assert hex2 == expected_hex(bundle2)
    assert hex2 != hex1


def test_model_header_replaced_not_repeated(tmp_path, monkeypatch):
    bundle = make_bundle("T")
    repo_root, file = run(
        tmp_path, monkeypatch, "r3", bundle,
        "# hotdocs-criterion: sha256:0000\nimport x",
    )
    content = field(file, "content")
    lines = content.split("\n")
    header_lines = [ln for ln in lines if ln.startswith(HEADER_PREFIX)]
    assert len(header_lines) == 1
    assert lines[0].startswith(HEADER_PREFIX)
    assert lines[0] == "# hotdocs-criterion: sha256:" + expected_hex(bundle)
    assert content == "# hotdocs-criterion: sha256:" + expected_hex(bundle) + "\nimport x"
    written = (repo_root / field(file, "path")).read_text(encoding="utf-8")
    assert written == content