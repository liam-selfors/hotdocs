# hotdocs-criterion: sha256:b63a3e628b2b89b6b03db6712e9a4de75d6a2a1113b688c6a74762f20cf0bb02
"""AC-DOCS-006: a render run makes no network call and no model call."""

import importlib
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

import docs_site_renderer


def _main():
    main = getattr(docs_site_renderer, "main", None)
    if main is None:
        cli = importlib.import_module("docs_site_renderer.cli")
        main = cli.main
    return main


def _write_corpus_graph(repo_root):
    graph = {
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
                    "component.md": "# Foo\n\nThe foo component <b>&</b>.\n",
                    "requirements/R-FOO-001.md": "# R-FOO-001\n\n**R-FOO-001** MUST foo.\n",
                },
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": False,
                "pinned_overrides": [],
                "owners": [],
                "documents": {
                    "component.md": "# Bar\n\nThe bar component.\n",
                },
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
    verification = repo_root / "verification"
    verification.mkdir(parents=True, exist_ok=True)
    path = verification / "corpus-graph.json"
    path.write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return path


def _write_fake_llm_endpoint(repo_root, log_path):
    base = repo_root / "gen" / "llm-endpoint"
    base.mkdir(parents=True, exist_ok=True)
    source = (
        "from pathlib import Path\n"
        "\n"
        "_LOG = Path(" + repr(str(log_path)) + ")\n"
        "\n"
        "\n"
        "def complete(*args, **kwargs):\n"
        "    with _LOG.open('a', encoding='utf-8') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    raise RuntimeError('model call made during a docs-site render')\n"
    )
    (base / "llm_endpoint.py").write_text(source, encoding="utf-8")


def test_ac_docs_006_render_makes_no_network_or_model_call(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    model_log = tmp_path / "model-calls.log"

    _write_corpus_graph(repo_root)
    _write_fake_llm_endpoint(repo_root, model_log)

    # No credentials for any model provider are available to the run.
    for name in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OLLAMA_HOST",
    ):
        monkeypatch.delenv(name, raising=False)

    attempts = []

    def _blocked(label):
        def _raise(*args, **kwargs):
            attempts.append(label)
            raise OSError("blocked during render: " + label)

        return _raise

    # Network: any connection attempt, DNS lookup or datagram send is recorded.
    monkeypatch.setattr(socket.socket, "connect", _blocked("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked("socket.connect_ex"))
    monkeypatch.setattr(socket.socket, "sendto", _blocked("socket.sendto"))
    monkeypatch.setattr(socket, "create_connection", _blocked("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", _blocked("socket.getaddrinfo"))
    monkeypatch.setattr(socket, "gethostbyname", _blocked("socket.gethostbyname"))

    # Model calls through a CLI provider (e.g. claude-cli) need a subprocess.
    class _NoPopen:
        def __init__(self, *args, **kwargs):
            attempts.append("subprocess.Popen")
            raise OSError("blocked during render: subprocess.Popen")

    monkeypatch.setattr(subprocess, "Popen", _NoPopen)
    monkeypatch.setattr(os, "system", _blocked("os.system"))
    if hasattr(os, "posix_spawn"):
        monkeypatch.setattr(os, "posix_spawn", _blocked("os.posix_spawn"))
    if hasattr(os, "posix_spawnp"):
        monkeypatch.setattr(os, "posix_spawnp", _blocked("os.posix_spawnp"))

    code = _main()(["--repo-root=" + str(repo_root), "--out=" + str(out_dir)])

    assert attempts == []
    assert not model_log.exists() or model_log.read_text(encoding="utf-8") == ""
    assert code == 0
    assert (out_dir / "index.html").is_file()