# hotdocs-criterion: sha256:7b3536dbcfc73e383db7f009926725e78e66793e526fec8c0c3450eb5cf39c87
import re
from pathlib import Path

import generator


FAKE_PYTHON_ADAPTER = (
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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, "
    "\"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def _plant_python_adapter(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "kind_python.py").write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")


def _cold_bundle():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "Foo component body. The foo function returns a greeting.",
        "interface": "foo() -> str",
        "constraints": "Pure Python only.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "Foo: a greeting producer.",
        "hint_code": None,
    }


def test_retry_feedback_is_distinct_bare_id_section_and_echoed(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_python_adapter(repo_root)

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo():\n"
            "    return 'hi'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        _cold_bundle(),
        "claude-sonnet-5",
        ["R-FOO-003"],
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert len(recorded) >= 1, "mock model was never called"
    prompt = recorded[-1]
    lines = prompt.split("\n")

    # A distinctly labeled section exists, after the bundle-derived sections.
    assert "## RETRY_FEEDBACK" in lines
    assert lines.index("## RETRY_FEEDBACK") > lines.index("## GLOSSARY")
    assert lines.index("## RETRY_FEEDBACK") > lines.index("## SPEC")

    retry = section(prompt, "## RETRY_FEEDBACK")
    retry_lines = [ln for ln in retry.split("\n") if ln.strip()]
    id_lines = [ln for ln in retry_lines if ln.startswith("- ")]
    assert id_lines == ["- R-FOO-003"]
    # One sentence, then exactly one id line: nothing else in the section.
    assert len(retry_lines) == 2
    assert re.findall(r"\bR-[A-Z]+-\d+\b", retry) == ["R-FOO-003"]

    # Not merged into any SpecBundle-derived section.
    for heading in (
        "## SPEC",
        "## INTERFACE",
        "## CONSTRAINTS",
        "## DEPENDENCY INTERFACES",
        "## DEPENDENCY CONTEXT",
        "## VARS",
        "## GLOSSARY",
    ):
        assert "R-FOO-003" not in section(prompt, heading)
    assert prompt.count("R-FOO-003") == 1

    # No acceptance-criterion content anywhere in the prompt.
    assert "```gherkin" not in prompt
    for ln in lines:
        stripped = ln.strip()
        for keyword in ("Given ", "Then ", "Scenario:", "Feature:"):
            assert not stripped.startswith(keyword), ln
    lowered = prompt.lower()
    assert "rationale" not in lowered
    assert "expected:" not in lowered
    assert "actual:" not in lowered
    assert "AC-FOO" not in prompt

    # The result echoes the caller's retry_feedback.
    assert field(result, "retry_feedback") == ["R-FOO-003"]