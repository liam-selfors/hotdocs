# hotdocs-criterion: sha256:fc3b547894fa79f0ca21616d377a0f68a28178ac32a8bd5dd7336bc7adc9fc92
import json
import re
from pathlib import Path

import generator


PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"python\"\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [\"bad.py:1: SyntaxError: x\"] if (Path(code_dir) / \"bad.py\").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, \"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo\n"
)


class Bundle:
    def __init__(self, **kwargs):
        self._data = dict(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def test_ac_gen_001(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")

    comp = repo_root / "specs" / "components" / "foo" / "component.md"
    comp.parent.mkdir(parents=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")

    log_path = tmp_path / "prompts.log"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(prompt) + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "ok\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    bundle = Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a" * 64,
        spec="SPEC-MARK",
        interface="IFACE-MARK",
        constraints="CONS-MARK",
        dependency_interfaces={"comp-bar": "DI-MARK"},
        dependency_context={"comp-bar": "DC-MARK"},
        dependency_usage={"comp-bar": ""},
        vars={"VAR-X": "VAR-MARK"},
        glossary="GLOSS-MARK",
        hint_code=None,
        spec_bundle_parts={},
    )

    generator.generate(bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend)

    assert log_path.exists(), "mock model was never called"
    lines = [l for l in log_path.read_text(encoding="utf-8").split("\n") if l]
    assert len(lines) == 1
    prompt = json.loads(lines[0])

    assert section(prompt, "## SPEC") == "SPEC-MARK"
    assert section(prompt, "## DEPENDENCY CONTEXT") == "### comp-bar\nDC-MARK"

    headings = [
        "## SPEC",
        "## INTERFACE",
        "## CONSTRAINTS",
        "## DEPENDENCY INTERFACES",
        "## DEPENDENCY CONTEXT",
        "## VARS",
        "## GLOSSARY",
    ]
    expected = {
        "IFACE-MARK": "## INTERFACE",
        "CONS-MARK": "## CONSTRAINTS",
        "DI-MARK": "## DEPENDENCY INTERFACES",
        "VAR-MARK": "## VARS",
        "GLOSS-MARK": "## GLOSSARY",
    }
    sections = {h: section(prompt, h) for h in headings}
    for marker, heading in expected.items():
        assert marker in sections[heading], (marker, heading, sections[heading])
        for other in headings:
            if other != heading:
                assert marker not in sections[other], (marker, other)

    prompt_lines = prompt.split("\n")
    for forbidden in ("## DEPENDENCY USAGE", "## HINT_CODE", "## RETRY_FEEDBACK"):
        assert forbidden not in prompt_lines, forbidden