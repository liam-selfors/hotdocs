# hotdocs-criterion: sha256:524711e7ddeafaa773c499083f5fce68c2d5353852eb0564a17db288a4f637f1
import hashlib
import json
import re
from pathlib import Path

import pytest

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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, "
    "\"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(component_id, title, sealed, source_path=None):
    lines = [
        "---",
        "id: " + component_id,
        "title: " + title,
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "sealed: " + ("true" if sealed else "false"),
    ]
    if source_path is not None:
        lines.append("source_path: " + source_path)
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    lines.append("")
    return "\n".join(lines)


def make_bundle(component_id, tag):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + hashlib.sha256(tag.encode("utf-8")).hexdigest(),
        "spec": "Spec for " + component_id,
        "interface": "Interface for " + component_id,
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def make_backend(log_path, filename):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": " + filename + "-----\n"
            "X = 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


@pytest.mark.parametrize("case", ["sealed", "pinned"])
def test_ac_gen_009_exempt_components_refused_without_model_call(tmp_path, monkeypatch, case):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)

    log_path = tmp_path / "model_calls.log"

    if case == "sealed":
        slug = "widget"
        component_id = "comp-widget"
        write(
            repo_root / "specs" / "components" / slug / "component.md",
            component_md(component_id, "Widget", True, "legacy/widget/"),
        )
        write(repo_root / "legacy" / "widget" / "widget.py", "ORIGINAL = True\n")
        filename = "widget.py"
        expected_reason = "sealed-component"
    else:
        slug = "gadget"
        component_id = "comp-gadget"
        write(
            repo_root / "specs" / "components" / slug / "component.md",
            component_md(component_id, "Gadget", False),
        )
        write(repo_root / "gen" / slug / "gadget.py", "PINNED = True\n")
        write(repo_root / "gen" / slug / ".overrides.json", json.dumps(["gadget.py"]))
        filename = "gadget.py"
        expected_reason = "pinned-override"

    bundle = make_bundle(component_id, "ac-gen-009-" + case)
    backend = make_backend(log_path, filename)

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=backend,
    )

    calls = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert calls == "", "mock model was called"

    assert field(result, "files") == {}
    assert field(result, "model_call_error") is None
    refused = field(result, "refused")
    assert isinstance(refused, str)
    assert refused == expected_reason