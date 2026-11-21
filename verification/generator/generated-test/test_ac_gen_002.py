# hotdocs-criterion: sha256:7a8375c6e3b2c4287f1dafb3c477d337dc2f5b11327fd1b71359501aa43429b0
import re
from pathlib import Path

import generator


PY_ADAPTER = (
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


def test_ac_gen_002_hint_code_in_own_labeled_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(PY_ADAPTER, encoding="utf-8")

    hint_a = "HINT_TOKEN_ALPHA_7f3a = 1\n"
    hint_b = "HINT_TOKEN_BETA_9c2d = 2\n"
    bundle = {
        "component_id": "comp-hintee",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "SPEC_TOKEN_ONE describes the component.",
        "interface": "INTERFACE_TOKEN_TWO def run() -> int",
        "constraints": "CONSTRAINTS_TOKEN_THREE",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "GLOSSARY_TOKEN_FOUR",
        "hint_code": {"zeta.py": hint_b, "alpha.py": hint_a},
    }

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": hintee.py-----\n"
            "def run():\n"
            "    return 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    generator.generate(bundle, "mock-model", repo_root=repo_root, llm_backend=backend)

    assert len(prompts) >= 1
    prompt = prompts[0]
    lines = prompt.split("\n")

    # hint_code has its own distinctly labeled section
    assert "## HINT_CODE" in lines
    hint_section = section(prompt, "## HINT_CODE")
    assert "--- hint file: alpha.py ---" in hint_section
    assert "--- end hint file: alpha.py ---" in hint_section
    assert "--- hint file: zeta.py ---" in hint_section
    assert "--- end hint file: zeta.py ---" in hint_section
    assert "HINT_TOKEN_ALPHA_7f3a = 1" in hint_section
    assert "HINT_TOKEN_BETA_9c2d = 2" in hint_section
    # files sorted by path
    assert hint_section.index("--- hint file: alpha.py ---") < hint_section.index("--- hint file: zeta.py ---")

    # hint section is separate from cold bundle fields
    cold_headings = ["## SPEC", "## INTERFACE", "## CONSTRAINTS", "## GLOSSARY"]
    cold_tokens = ["SPEC_TOKEN_ONE", "INTERFACE_TOKEN_TWO", "CONSTRAINTS_TOKEN_THREE", "GLOSSARY_TOKEN_FOUR"]
    for heading, token in zip(cold_headings, cold_tokens):
        assert heading in lines
        cold_text = section(prompt, heading)
        assert token in cold_text
        assert "HINT_TOKEN_ALPHA_7f3a" not in cold_text
        assert "HINT_TOKEN_BETA_9c2d" not in cold_text
        assert "hint file:" not in cold_text
        assert token not in hint_section

    # hint code appears only within its own section
    assert prompt.count("HINT_TOKEN_ALPHA_7f3a") == 1
    assert prompt.count("HINT_TOKEN_BETA_9c2d") == 1
    # and that section comes after the cold sections
    assert lines.index("## HINT_CODE") > lines.index("## GLOSSARY")