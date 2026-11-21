# hotdocs-criterion: sha256:7c0b214befce634469e3345f470c1b6bc7adc92d44067c77af724681363262a1
import re
from pathlib import Path

import generator


PYTHON_ADAPTER_SOURCE = (
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


def _plant_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER_SOURCE, encoding="utf-8")


def _make_mock(log_path, calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "VALUE = 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def test_ac_gen_002_hint_code_in_own_labeled_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "model_calls.log"
    calls = []
    backend = _make_mock(log_path, calls)

    hint_code = {
        "zeta_mod.py": "HINTMARKERZETA = 2\n",
        "alpha_mod.py": "HINTMARKERALPHA = 1\n",
    }
    bundle = {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "COLDSPECMARKER the widget maker makes widgets.",
        "interface": "COLDINTERFACEMARKER make_widget() -> str",
        "constraints": "COLDCONSTRAINTSMARKER no network.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "COLDGLOSSARYMARKER widget: a thing.",
        "hint_code": hint_code,
    }

    generator.generate(
        bundle,
        "anthropic:claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=backend,
    )

    assert log_path.exists(), "mock model was never called"
    assert len(calls) >= 1
    prompt = calls[-1]
    lines = prompt.split("\n")

    # hint_code has its own, distinctly labeled section
    assert "## HINT_CODE" in lines
    hint_text = section(prompt, "## HINT_CODE")

    # each hint file is labeled and present, sorted by path
    a_begin = hint_text.index("--- hint file: alpha_mod.py ---")
    a_end = hint_text.index("--- end hint file: alpha_mod.py ---")
    z_begin = hint_text.index("--- hint file: zeta_mod.py ---")
    z_end = hint_text.index("--- end hint file: zeta_mod.py ---")
    assert a_begin < a_end < z_begin < z_end
    assert "HINTMARKERALPHA = 1" in hint_text[a_begin:a_end]
    assert "HINTMARKERZETA = 2" in hint_text[z_begin:z_end]

    # hint content appears only in the HINT_CODE section
    assert prompt.count("HINTMARKERALPHA") == 1
    assert prompt.count("HINTMARKERZETA") == 1

    # cold bundle fields remain in their own sections, separate from hint_code
    cold = {
        "## SPEC": "COLDSPECMARKER",
        "## INTERFACE": "COLDINTERFACEMARKER",
        "## CONSTRAINTS": "COLDCONSTRAINTSMARKER",
        "## GLOSSARY": "COLDGLOSSARYMARKER",
    }
    for heading, marker in cold.items():
        assert heading in lines
        text = section(prompt, heading)
        assert marker in text
        assert "HINTMARKERALPHA" not in text
        assert "HINTMARKERZETA" not in text
        assert "--- hint file:" not in text
        assert marker not in hint_text

    # the HINT_CODE section is distinct from, and after, the cold sections
    hint_idx = lines.index("## HINT_CODE")
    for heading in cold:
        assert lines.index(heading) < hint_idx