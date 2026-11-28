# hotdocs-criterion: sha256:acc9641f7264209b97ab86b10a28e8e273dc9cf8ed7a8f86adfece8966f32cad
"""AC-DOCS-006: a render run makes no network call or model call at any point.

Covers R-DOCS-006: docs-site-renderer MUST make no model calls; it is a pure
rendering step.

A model call reaches its provider either over the network (anthropic, openai,
openai-compatible, gemini, ollama) or by starting a process (claude-cli). This
test blocks and records every socket connection, DNS lookup and process start
while the renderer runs. It then asserts that none was attempted. It checks
both the library entry point `render_docs_site` and the CLI `main`.
"""

import json
import os
import socket
import subprocess
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import docs_site_renderer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _graph_dict():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "# Foo\n\nThe foo component.\n",
                    "requirements/R-FOO-001.md": "# R-FOO-001\n\n**R-FOO-001** - MUST foo.\n",
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
                "documents": {"component.md": "# Bar\n"},
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
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


@dataclass
class _CorpusGraph:
    """Stand-in with CorpusGraph's documented attributes and methods."""

    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


@pytest.fixture
def no_egress(monkeypatch):
    """Block and record every network or process-start attempt."""
    attempts = []

    def _blocked(kind):
        def _fn(*args, **kwargs):
            attempts.append((kind, repr(args)[:200]))
            raise OSError("AC-DOCS-006: " + kind + " is forbidden during a render run")

        return _fn

    monkeypatch.setattr(socket.socket, "connect", _blocked("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked("socket.connect_ex"))
    monkeypatch.setattr(socket.socket, "sendto", _blocked("socket.sendto"))
    monkeypatch.setattr(socket, "create_connection", _blocked("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", _blocked("socket.getaddrinfo"))
    monkeypatch.setattr(socket, "gethostbyname", _blocked("socket.gethostbyname"))
    monkeypatch.setattr(subprocess, "Popen", _blocked("subprocess.Popen"))
    monkeypatch.setattr(os, "system", _blocked("os.system"))
    if hasattr(os, "posix_spawn"):
        monkeypatch.setattr(os, "posix_spawn", _blocked("os.posix_spawn"))
    if hasattr(os, "posix_spawnp"):
        monkeypatch.setattr(os, "posix_spawnp", _blocked("os.posix_spawnp"))
    for name in ("execv", "execve", "execvp", "execvpe", "fork"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, _blocked("os." + name))

    # Make sure no credentials could enable a model call even if one were tried.
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    return attempts


def test_render_docs_site_makes_no_network_or_model_call(tmp_path, no_egress):
    g = _graph_dict()
    graph = _CorpusGraph(nodes=g["nodes"], edges=g["edges"], aggregates=g["aggregates"])
    out_dir = tmp_path / "site"

    docs_site_renderer.render_docs_site(graph, out_dir)

    assert no_egress == [], "render run attempted network/model egress: " + repr(no_egress)
    assert (out_dir / "index.html").is_file()


def test_cli_build_makes_no_network_or_model_call(tmp_path, no_egress):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(_graph_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    from docs_site_renderer import cli

    code = cli.main(["--repo-root=" + str(repo_root), "--out=" + str(out_dir)])

    assert no_egress == [], "render run attempted network/model egress: " + repr(no_egress)
    assert code == 0
    assert (out_dir / "index.html").is_file()