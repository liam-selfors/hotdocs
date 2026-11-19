# hotdocs-criterion: sha256:c76e88c93d623eaf8daa3e40e9964874628c7756cb00a98b318f5a3d8d82529e
import hashlib
import json
import re

import test_author


KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(testing="T"):
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "Given a\nWhen b\nThen c",
        "requirement_text": "R-X-1 MUST c",
        "interface": "I",
        "glossary": "G",
        "dependency_interfaces": {},
        "testing": testing,
    }


def expected_hex(bundle):
    data = {k: bundle.get(k, "") for k in KEYS}
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG = " + repr(str(log_path)) + "\n"
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
        "        return {'ok': True, 'findings': [], 'tests_run': 1, 'tests_reached': 1}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(content, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("call\n")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + content
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def setup_repo(tmp_path, name, monkeypatch):
    repo_root = tmp_path / name
    repo_root.mkdir()
    probe_log = tmp_path / (name + "-probe.log")
    write_probe_stand_in(repo_root, probe_log)
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return repo_root


def read_written(repo_root, result):
    file = field(result, "file")
    assert file is not None
    path = field(file, "path")
    return (repo_root / path).read_bytes().decode("utf-8")


def test_criterion_header_line(tmp_path, monkeypatch):
    # Scenario 1: header computed from the bundle, then the model's content.
    bundle1 = make_bundle("T")
    hex1 = expected_hex(bundle1)
    header1 = "# hotdocs-criterion: sha256:" + hex1
    repo1 = setup_repo(tmp_path, "r1", monkeypatch)
    log1 = tmp_path / "model1.log"
    result1 = test_author.author_test(
        bundle1, "mock", repo_root=repo1, llm_backend=make_backend("import x", log1)
    )
    assert field(result1, "model_call_error") is None
    expected1 = header1 + "\nimport x"
    assert field(field(result1, "file"), "content") == expected1
    assert read_written(repo1, result1) == expected1
    assert re.fullmatch(r"[0-9a-f]{64}", hex1)

    # Scenario 2: a different testing value gives a different header hex.
    bundle2 = make_bundle("T2")
    repo2 = setup_repo(tmp_path, "r2", monkeypatch)
    log2 = tmp_path / "model2.log"
    result2 = test_author.author_test(
        bundle2, "mock", repo_root=repo2, llm_backend=make_backend("import x", log2)
    )
    assert field(result2, "model_call_error") is None
    content2 = field(field(result2, "file"), "content")
    first2 = content2.split("\n", 1)[0]
    assert first2.startswith("# hotdocs-criterion: sha256:")
    hex2 = first2[len("# hotdocs-criterion: sha256:"):]
    assert hex2 == expected_hex(bundle2)
    assert hex2 != hex1

    # Scenario 3: a model-supplied header line is replaced, never repeated.
    bundle3 = make_bundle("T")
    repo3 = setup_repo(tmp_path, "r3", monkeypatch)
    log3 = tmp_path / "model3.log"
    result3 = test_author.author_test(
        bundle3,
        "mock",
        repo_root=repo3,
        llm_backend=make_backend("# hotdocs-criterion: sha256:0000\nimport x", log3),
    )
    assert field(result3, "model_call_error") is None
    content3 = field(field(result3, "file"), "content")
    lines3 = content3.split("\n")
    header_lines = [ln for ln in lines3 if ln.startswith("# hotdocs-criterion:")]
    assert len(header_lines) == 1
    assert lines3[0] == header1
    assert "sha256:0000\n" not in content3 + "\n" or lines3[0] == header1
    assert content3 == header1 + "\nimport x"

    # Scenario 4: a cache hit in the first repo also carries the header.
    monkeypatch.chdir(repo1)
    never_log = tmp_path / "never.log"
    result4 = test_author.author_test(
        make_bundle("T"),
        "mock",
        repo_root=repo1,
        llm_backend=make_backend("import y", never_log),
    )
    assert not never_log.exists() or never_log.read_text(encoding="utf-8") == ""
    assert field(result4, "cache_hit") is True
    content4 = field(field(result4, "file"), "content")
    assert content4.split("\n", 1)[0] == header1
    assert content4.startswith(header1 + "\n")