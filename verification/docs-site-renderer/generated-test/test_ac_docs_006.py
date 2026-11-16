"""AC-DOCS-006: a render run makes no network call and no model call.

Covers R-DOCS-006: the docs-site renderer MUST make no model calls -- it is
a pure rendering step.
"""

import json
import socket
import subprocess
import sys
import types
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import docs_site_renderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class CorpusGraph:
    """Stand-in matching corpus-graph-builder's documented CorpusGraph shape."""

    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "aggregates": self.aggregates,
        }

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
            + "\n"
        ).encode("utf-8")


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [pipeline-team]
depends_on: [comp-bar]
realizes: [P-ZERO-EDIT]
uses_var: [VAR-FOO-URL]
sealed: false
---

# Foo

Foo does <things> & stuff.
"""

BAR_MD = """---
id: comp-bar
title: Bar
status: draft
owners: [infra-team]
depends_on: []
realizes: []
uses_var: []
sealed: true
source_path: legacy/bar/
---

# Bar

Bar is sealed.
"""


def make_graph():
    nodes = {
        "P-ZERO-EDIT": {"type": "capability"},
        "VAR-FOO-URL": {"type": "var"},
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": COMPONENT_MD,
                "requirements/R-FOO-001.md": "**R-FOO-001** -- MUST foo.\n",
            },
        },
        "comp-bar": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["infra-team"],
            "documents": {"component.md": BAR_MD},
        },
    }
    edges = [
        {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
        {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
    ]
    edges.sort(key=lambda e: (e["from"], e["to"], e["kind"]))
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def write_fake_llm_endpoint(repo_root: Path, log_path: Path):
    """A fake llm-endpoint that logs any invocation to a file."""
    dep_dir = repo_root / "gen" / "llm-endpoint"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "llm_endpoint.py").write_text(
        "import json\n"
        f"_LOG = {str(log_path)!r}\n"
        "def _log(name, args, kwargs):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': name, 'args': repr(args),"
        " 'kwargs': repr(kwargs)}) + '\\n')\n"
        "def complete(*args, **kwargs):\n"
        "    _log('complete', args, kwargs)\n"
        "    raise RuntimeError('model call made during docs-site render')\n",
        encoding="utf-8",
    )


MODEL_CLI_WORDS = ("claude", "ollama", "anthropic", "openai", "gemini")


@pytest.fixture
def guard(monkeypatch, tmp_path):
    """Block and record every network, model-SDK and model-CLI call."""
    log_path = tmp_path / "forbidden_calls.log"

    def record(kind, detail):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": kind, "detail": repr(detail)}) + "\n")

    # --- network ---
    def blocked_connect(self, address, *a, **k):
        record("socket.connect", address)
        raise OSError("network blocked by test")

    def blocked_connect_ex(self, address, *a, **k):
        record("socket.connect_ex", address)
        raise OSError("network blocked by test")

    def blocked_create_connection(address, *a, **k):
        record("socket.create_connection", address)
        raise OSError("network blocked by test")

    def blocked_getaddrinfo(host, *a, **k):
        record("socket.getaddrinfo", host)
        raise socket.gaierror("network blocked by test")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_connect_ex)
    monkeypatch.setattr(socket, "create_connection", blocked_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", blocked_getaddrinfo)

    # --- model SDKs: any import yields a module that logs any attribute use ---
    def make_sdk(name):
        mod = types.ModuleType(name)

        def __getattr__(attr):
            if attr.startswith("__"):
                raise AttributeError(attr)
            record("sdk", f"{name}.{attr}")
            raise RuntimeError(f"model SDK {name} used during docs-site render")

        mod.__getattr__ = __getattr__
        return mod

    for sdk in ("anthropic", "openai", "ollama", "google.generativeai"):
        monkeypatch.setitem(sys.modules, sdk, make_sdk(sdk))

    # --- model CLIs via subprocess ---
    real_popen = subprocess.Popen

    class GuardedPopen(real_popen):
        def __init__(self, args, *a, **k):
            text = args if isinstance(args, str) else " ".join(map(str, args))
            if any(w in text.lower() for w in MODEL_CLI_WORDS):
                record("subprocess", text)
                raise OSError("model CLI blocked by test")
            super().__init__(args, *a, **k)

    monkeypatch.setattr(subprocess, "Popen", GuardedPopen)

    # Make any accidental provider configuration inert.
    for env in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(env, raising=False)

    return log_path


def read_log(path: Path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def all_files(root: Path):
    return [p for p in root.rglob("*") if p.is_file()]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_library_render_makes_no_network_or_model_call(tmp_path, guard):
    out_dir = tmp_path / "site"
    graph = make_graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    assert read_log(guard) == [], (
        "render_docs_site made a network or model call: " + "\n".join(read_log(guard))
    )
    assert out_dir.is_dir()
    assert all_files(out_dir), "render produced no files"


def test_cli_render_makes_no_network_or_model_call(tmp_path, guard):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph = make_graph()
    (repo_root / "verification" / "corpus-graph.json").write_bytes(
        graph.to_json_bytes()
    )

    model_log = tmp_path / "llm_endpoint_calls.log"
    write_fake_llm_endpoint(repo_root, model_log)

    out_dir = tmp_path / "cli-site"

    from docs_site_renderer import cli

    code = cli.main([f"--repo-root={repo_root}", f"--out={out_dir}"])

    assert code == 0
    assert read_log(guard) == [], (
        "docs-site build made a network or model call: " + "\n".join(read_log(guard))
    )
    assert read_log(model_log) == [], (
        "docs-site build invoked llm-endpoint: " + "\n".join(read_log(model_log))
    )
    assert out_dir.is_dir()
    assert all_files(out_dir), "render produced no files"