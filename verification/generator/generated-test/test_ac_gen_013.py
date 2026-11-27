# hotdocs-criterion: sha256:ad0df73ec224adb7740997cee3ae4aacf1c00c7e78b919638cb4869c882fc0d6
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
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


class Bundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "a" * 64,
        spec="# Widget Maker\n\nMakes widgets.\n\n# R-WIDGET-001\n\n**R-WIDGET-001** - It MUST make a widget.",
        interface="# Library\n\n```\nmake() -> str\n```",
        constraints="# Constraints\n\nNone in particular.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Widget** - a thing that is made.",
        hint_code=None,
        spec_bundle_parts={},
    )


def test_ac_gen_013_retry_feedback_is_bare_distinct_section_and_echoed(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    (repo_root / "gen" / "kind-python").mkdir(parents=True)
    (repo_root / "gen" / "kind-python" / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    monkeypatch.chdir(repo_root)

    log_dir = tmp_path / "log"
    log_dir.mkdir()
    calls_log = log_dir / "calls.log"

    def mock_backend(prompt, model, **params):
        n = len(list(log_dir.glob("prompt_*.txt")))
        (log_dir / ("prompt_" + str(n) + ".txt")).write_text(prompt, encoding="utf-8")
        with open(calls_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make():\n"
            "    return \"widget\"\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        make_bundle(),
        "mock-model",
        ["R-FOO-003"],
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The mock was called exactly once and recorded its input.
    assert calls_log.exists(), "mock model was never called"
    assert calls_log.read_text(encoding="utf-8").splitlines() == ["call"]
    prompt = (log_dir / "prompt_0.txt").read_text(encoding="utf-8")

    # retry_feedback is its own, distinctly labeled section.
    lines = prompt.split("\n")
    assert lines.count("## RETRY_FEEDBACK") == 1
    body = section(prompt, "## RETRY_FEEDBACK")

    # It contains only the bare R-id "R-FOO-003".
    assert re.findall(r"\bR-[A-Z0-9]+-\d+\b", body) == ["R-FOO-003"]
    id_lines = [ln for ln in body.split("\n") if ln.startswith("- ")]
    assert id_lines == ["- R-FOO-003"]
    non_empty = [ln for ln in body.split("\n") if ln.strip()]
    assert non_empty[-1] == "- R-FOO-003"
    assert len(non_empty) == 2, "expected one sentence then one id line, got: " + repr(body)

    # Never merged with the bundle's fields: the id appears only in that section.
    assert prompt.count("R-FOO-003") == 1
    for heading in ("## SPEC", "## INTERFACE", "## CONSTRAINTS", "## GLOSSARY"):
        assert "R-FOO-003" not in section(prompt, heading)

    # No Gherkin text, rationale, or expected/actual values anywhere in the prompt.
    for ln in lines:
        stripped = ln.strip()
        for kw in ("Given ", "When ", "Then ", "And ", "Scenario:", "Feature:"):
            assert not stripped.startswith(kw), "Gherkin-like line in prompt: " + repr(ln)
    assert "```gherkin" not in prompt
    lowered_body = body.lower()
    for word in ("given", "then", "rationale", "expected", "actual", "ac-"):
        assert word not in lowered_body, "criterion content in retry feedback: " + repr(body)
    assert not re.search(r"\bAC-[A-Z0-9]+-\d+\b", prompt)
    assert not re.search(r"(?im)^\s*rationale\s*:", prompt)
    assert not re.search(r"(?im)^\s*(expected|actual)\s*[:=]", prompt)

    # The result echoes the caller's retry_feedback.
    assert field(result, "retry_feedback") == ["R-FOO-003"]
    assert field(result, "cache_hit") is False
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None