# hotdocs-criterion: sha256:71d33d195deba66cec0b12424a1cdca448310efc07fe5824ec70dd20be952a5c
import hashlib
import json
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


TEST_REL = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
TEST_CONTENT = "def test_x():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    # The python kind adapter, planted so nothing depends on the tool's own.
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # The realizing component comp-foo.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        "FOO_IFACE",
    )
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "def foo():\n"
        "    return 1\n",
    )

    # The glossary.
    _write(repo_root / "specs" / "glossary.md", "GLOSS")

    # The capability P-X with one generated-test scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )

    # Fake test-author: records each bundle it receives.
    calls = repo_root / "calls.jsonl"
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "import json\n"
        "\n"
        "CALLS = " + repr(str(calls)) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(CALLS, \"a\", encoding=\"utf-8\") as fh:\n"
        "        fh.write(json.dumps(bundle, default=str) + \"\\n\")\n"
        "    return {\"model_call_error\": None, \"file\": {\"path\": "
        + repr(TEST_REL)
        + ", \"content\": "
        + repr(TEST_CONTENT)
        + "}}\n",
    )

    # Fake llm-endpoint (not expected to be used by a generated-test scenario).
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )
    return calls


def _read_calls(calls):
    if not calls.is_file():
        return []
    return [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines() if line.strip()]


def _hex_for(bundle):
    payload = {
        "criterion_text": bundle["criterion_text"],
        "requirement_text": bundle["requirement_text"],
        "interface": bundle["interface"],
        "glossary": bundle["glossary"],
        "testing": "",
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("header_mode,expected_calls", [("current", 1), ("stale", 2)])
def test_committed_test_reused_only_when_header_current(tmp_path, header_mode, expected_calls):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    calls = _build_fixture(repo_root)

    capability_scenario_verifier.run_capability_gates("P-X", repo_root, "m")

    recorded = _read_calls(calls)
    assert len(recorded) == 1, recorded

    if header_mode == "current":
        header = "# hotdocs-criterion: sha256:" + _hex_for(recorded[0])
    else:
        header = "# hotdocs-criterion: sha256:0000"

    test_file = repo_root / TEST_REL
    _write(test_file, header + "\n" + TEST_CONTENT)

    provenance = repo_root / "verification" / "capabilities" / "P-X" / ".provenance.json"
    if provenance.exists():
        provenance.unlink()
    assert not provenance.exists()

    capability_scenario_verifier.run_capability_gates("P-X", repo_root, "m")

    recorded = _read_calls(calls)
    assert len(recorded) == expected_calls, recorded