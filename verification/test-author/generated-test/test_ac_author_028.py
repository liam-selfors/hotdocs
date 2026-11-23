# hotdocs-criterion: sha256:e063856aeb1f278efac012e004cc42471268e300c5a7b108f8975c38beccb330
import hashlib
import json
import re

import test_author


HEADER_PREFIX = "# hotdocs-criterion:"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(testing):
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
    data = {
        k: bundle[k]
        for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    }
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_probe_stand_in(repo_root, log_path):
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
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'test_source': test_source}) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_repo(tmp_path, name, monkeypatch):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-probe.log")
    write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return repo_root


def make_mock(file_content, calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
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


def never_called(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "must not be called"},
        }

    return backend


def run(bundle, repo_root, backend):
    return test_author.author_test(bundle, "mock", repo_root=repo_root, llm_backend=backend)


def written_text(repo_root, result):
    path = field(field(result, "file"), "path")
    return (repo_root / path).read_bytes().decode("utf-8")


def test_header_line_is_computed_from_bundle(tmp_path, monkeypatch):
    # Scenario 1: header + "\n" + model content, both returned and written.
    bundle = make_bundle("T")
    hex1 = expected_hex(bundle)
    header1 = "# hotdocs-criterion: sha256:" + hex1
    repo1 = make_repo(tmp_path, "r1", monkeypatch)
    calls1 = []
    result1 = run(bundle, repo1, make_mock("import x", calls1))
    assert field(result1, "model_call_error") is None
    assert len(calls1) >= 1
    content1 = field(field(result1, "file"), "content")
    assert content1 == header1 + "\n" + "import x"
    assert written_text(repo1, result1) == header1 + "\n" + "import x"
    assert re.fullmatch(r"[0-9a-f]{64}", hex1)

    # Scenario 2: a different testing value gives a different hex.
    bundle2 = make_bundle("T2")
    repo2 = make_repo(tmp_path, "r2", monkeypatch)
    result2 = run(bundle2, repo2, make_mock("import x", []))
    content2 = field(field(result2, "file"), "content")
    first2 = content2.split("\n", 1)[0]
    assert first2.startswith("# hotdocs-criterion: sha256:")
    hex2 = first2[len("# hotdocs-criterion: sha256:"):]
    assert hex2 == expected_hex(bundle2)
    assert hex2 != hex1

    # Scenario 3: a model-supplied header line is replaced, never repeated.
    repo3 = make_repo(tmp_path, "r3", monkeypatch)
    result3 = run(
        bundle, repo3,
        make_mock("# hotdocs-criterion: sha256:0000\nimport x", []),
    )
    content3 = field(field(result3, "file"), "content")
    lines3 = content3.split("\n")
    header_lines = [ln for ln in lines3 if ln.startswith(HEADER_PREFIX)]
    assert len(header_lines) == 1
    assert lines3[0] == header1
    assert content3 == header1 + "\n" + "import x"

    # Scenario 4: cache hit in repo1 carries the same correct header.
    monkeypatch.chdir(repo1)
    hit_calls = []
    result4 = run(bundle, repo1, never_called(hit_calls))
    assert hit_calls == []
    assert field(result4, "cache_hit") is True
    content4 = field(field(result4, "file"), "content")
    assert content4.split("\n", 1)[0] == header1
    assert content4.startswith(header1 + "\n")