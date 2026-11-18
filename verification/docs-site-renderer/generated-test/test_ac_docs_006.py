# hotdocs-criterion: sha256:b58a432ba6a2a54a20fa28aab404c5945d2569391eb0a90224fe9c3449aed003
import importlib.util
import json
import socket
import subprocess
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import docs_site_renderer


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


MODEL_CLI_WORDS = ("claude", "ollama", "anthropic", "openai", "gemini")


def graph_dict():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\n---\n# Foo <b>&\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** - MUST foo.\n",
                },
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": [],
                "documents": {},
            },
            "VAR-FOO-URL": {"type": "var"},
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.5,
            "orphan_var_rate": 0.0,
        },
    }


@dataclass
class _StandInCorpusGraph:
    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def make_graph():
    d = graph_dict()
    cls = None
    try:
        gen = next(
            p for p in Path(docs_site_renderer.__file__).resolve().parents if p.name == "gen"
        )
        base = gen / "corpus-graph-builder"
        flat = base / "corpus_graph_builder.py"
        path = flat if flat.is_file() else base / "corpus_graph_builder" / "__init__.py"
        if path.is_file():
            mod = load_module(path, "corpus_graph_builder")
            cls = getattr(mod, "CorpusGraph", None)
    except Exception:
        cls = None
    if cls is not None:
        try:
            return cls(nodes=d["nodes"], edges=d["edges"], aggregates=d["aggregates"])
        except Exception:
            pass
    return _StandInCorpusGraph(nodes=d["nodes"], edges=d["edges"], aggregates=d["aggregates"])


def write_fixture(repo_root, log_path):
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "---\n"
        "# Foo\n"
    )
    (comp / "requirements" / "R-FOO-001.md").write_text("**R-FOO-001** - MUST foo.\n")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: judged\n"
    )
    ver = repo_root / "verification"
    ver.mkdir(parents=True)
    (ver / "corpus-graph.json").write_text(
        json.dumps(graph_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    )
    fake_dir = repo_root / "gen" / "llm-endpoint"
    fake_dir.mkdir(parents=True)
    src = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def complete(*args, **kwargs):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('complete called' + chr(10))\n"
        "    raise RuntimeError('model call forbidden in docs-site render')\n"
    )
    (fake_dir / "llm_endpoint.py").write_text(src)


@pytest.fixture
def guards(monkeypatch):
    calls = {"network": [], "model_subprocess": []}

    def deny(name):
        def _deny(*args, **kwargs):
            calls["network"].append((name, repr(args)))
            raise OSError("network access forbidden in test: " + name)
        return _deny

    monkeypatch.setattr(socket.socket, "connect", deny("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", deny("socket.connect_ex"))
    monkeypatch.setattr(socket, "create_connection", deny("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", deny("getaddrinfo"))

    real_popen = subprocess.Popen

    class GuardPopen(real_popen):
        def __init__(self, args, *a, **kw):
            text = repr(args).lower()
            if any(w in text for w in MODEL_CLI_WORDS):
                calls["model_subprocess"].append(text)
                raise OSError("model CLI subprocess forbidden in test")
            super().__init__(args, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", GuardPopen)

    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    return calls


def _files_under(d):
    return [p for p in Path(d).rglob("*") if p.is_file()]


def test_library_render_makes_no_network_or_model_call(tmp_path, monkeypatch, guards):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "model_calls.log"
    write_fixture(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    out_dir = tmp_path / "out-lib"
    docs_site_renderer.render_docs_site(make_graph(), out_dir)

    assert guards["network"] == []
    assert guards["model_subprocess"] == []
    assert not log_path.exists()
    assert out_dir.is_dir()
    assert _files_under(out_dir)


def test_cli_render_makes_no_network_or_model_call(tmp_path, monkeypatch, guards):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "model_calls.log"
    write_fixture(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    spec_path = Path(docs_site_renderer.__file__).resolve().parent / "cli.py"
    cli = load_module(spec_path, "docs_site_renderer.cli")

    out_dir = tmp_path / "out-cli"
    code = cli.main(["--repo-root=" + str(repo_root), "--out=" + str(out_dir)])

    assert code == 0
    assert guards["network"] == []
    assert guards["model_subprocess"] == []
    assert not log_path.exists()
    assert out_dir.is_dir()
    assert _files_under(out_dir)