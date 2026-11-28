# hotdocs-criterion: sha256:49f7870767fe6960a412ef83f8fed0ba2fbd90f1fb9b7a3ae594f0e70bb06120
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
        k: bundle.get(k, "")
        for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plant_probe(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, " + repr("a") + ", encoding=" + repr("utf-8") + ") as f:\n"
        "        f.write(json.dumps(test_source) + " + repr("\n") + ")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(content):
    def backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + content
            + "\n-----END FILE " + nonce + "-----"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def run(tmp_path, monkeypatch, name, bundle, content):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-probe.log")
    plant_probe(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_backend(content)
    )
    assert field(result, "model_call_error") is None
    file_info = field(result, "file")
    assert file_info is not None
    path = field(file_info, "path")
    returned = field(file_info, "content")
    written = (repo_root / path).read_bytes().decode("utf-8")
    return returned, written


def header_hex(content):
    first = content.split("\n", 1)[0]
    prefix = HEADER_PREFIX + " sha256:"
    assert first.startswith(prefix)
    return first[len(prefix):]


def test_criterion_header_computed_from_bundle(tmp_path, monkeypatch):
    # Scenario 1: header is computed from the bundle and prepended.
    bundle1 = make_bundle("T")
    hex1 = expected_hex(bundle1)
    assert re.fullmatch(r"[0-9a-f]{64}", hex1)
    expected1 = "# hotdocs-criterion: sha256:" + hex1 + "\n" + "import x"

    returned1, written1 = run(tmp_path, monkeypatch, "r1", bundle1, "import x")
    assert returned1 == expected1
    assert written1 == expected1

    # Scenario 2: changing testing changes the header's hex.
    bundle2 = make_bundle("T2")
    returned2, written2 = run(tmp_path, monkeypatch, "r2", bundle2, "import x")
    hex2 = header_hex(returned2)
    assert hex2 != header_hex(returned1)
    assert header_hex(written2) == hex2
    assert hex2 == expected_hex(bundle2)

    # Scenario 3: a model-supplied header line is replaced, never repeated.
    bundle3 = make_bundle("T")
    returned3, written3 = run(
        tmp_path, monkeypatch, "r3", bundle3,
        "# hotdocs-criterion: sha256:0000\nimport x",
    )
    for content in (returned3, written3):
        lines = content.split("\n")
        header_lines = [ln for ln in lines if ln.startswith(HEADER_PREFIX)]
        assert len(header_lines) == 1
        assert lines[0].startswith(HEADER_PREFIX)
        assert header_hex(content) == expected_hex(bundle3)
        assert content == "# hotdocs-criterion: sha256:" + expected_hex(bundle3) + "\nimport x"