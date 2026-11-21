# hotdocs-criterion: sha256:48d6f74423b04914b9b8bd0f8a7adde6ef2b1ff43146ff0073791f1e58a202ec
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def _bundle():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "Foo component spec body. It provides a constant X.",
        "interface": "Library: X: int",
        "constraints": "No network access.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "- **Foo** - a thing.",
        "hint_code": None,
    }


def test_ac_gen_013_retry_feedback_is_bare_ids_in_own_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path

    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            + "X = 1\n"
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        _bundle(),
        "claude-sonnet-5",
        ["R-FOO-003"],
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert len(recorded) == 1, "mock model should have been called exactly once"
    prompt = recorded[0]
    lines = prompt.split("\n")

    # Distinct, labeled section.
    assert "## RETRY_FEEDBACK" in lines
    assert "## GLOSSARY" in lines
    assert lines.index("## RETRY_FEEDBACK") > lines.index("## GLOSSARY")

    fb = section(prompt, "## RETRY_FEEDBACK")
    fb_lines = [ln for ln in fb.split("\n") if ln.strip()]
    id_lines = [ln for ln in fb_lines if ln.startswith("- ")]
    assert id_lines == ["- R-FOO-003"]
    other_lines = [ln for ln in fb_lines if not ln.startswith("- ")]
    assert len(other_lines) <= 1, "only one introductory sentence expected besides id lines"
    for ln in other_lines:
        assert not re.search(r"R-[A-Z0-9]+-\d+", ln)

    # The id appears only in its own section, never merged into bundle fields.
    assert prompt.count("R-FOO-003") == 1

    # No Gherkin text, rationale, or expected/actual values anywhere.
    assert "```gherkin" not in prompt
    assert not re.search(r"(?m)^\s*(Given|Then|Scenario:|Feature:)\b", prompt)
    assert "rationale" not in prompt.lower()
    assert not re.search(r"(?i)\bexpected\s*:", prompt)
    assert not re.search(r"(?i)\bactual\s*:", prompt)
    assert "AC-FOO-" not in prompt

    # Result echoes retry_feedback.
    assert field(result, "retry_feedback") == ["R-FOO-003"]
    assert field(result, "cache_hit") is False
    assert field(result, "refused") is None
    assert field(result, "model_call_error") is None
    assert field(result, "files")