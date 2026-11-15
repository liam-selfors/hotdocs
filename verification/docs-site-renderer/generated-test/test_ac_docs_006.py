"""AC-DOCS-006 (Covers: R-DOCS-006).

Given a render run
When it executes
Then no network call or model call occurs at any point
"""

import docs_site_renderer

import importlib
import json
import socket
import subprocess
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class _Graph:
    """Stand-in carrying exactly the documented CorpusGraph shape."""

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

    def __getitem__(self, key):
        return self.to_dict()[key]


def _graph_dict():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
            "comp-foo": {
                "type": "component",
                "verification": {
                    "requirement_results": {"R-FOO-001": "pass"},
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "kind": "generated-test",
                            "result": "pass",
                        }
                    ],
                },
                "provenance": {
                    "component_id": "comp-foo",
                    "generated_at": "2026-01-01T00:00:00Z",
                    "model": "anthropic:claude-sonnet-5",
                },
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\n"
                    "owners: [pipeline-team]\n---\n\n# Foo <b>bold</b> & co\n"
                    "See https://example.invalid/should-not-be-fetched\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** — MUST foo.\n",
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
                "documents": {
                    "component.md": "---\nid: comp-bar\ntitle: Bar\nstatus: draft\n"
                    "owners: [pipeline-team]\n---\n\n# Bar\n",
                },
            },
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


def _sorted_edges(edges):
    return sorted(edges, key=lambda e: (e["from"], e["to"], e["kind"]))


_FAKE_LLM_ENDPOINT = '''
import json as _json

_LOG = {log!r}


def _record(name, args, kwargs):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({{"fn": name, "args": repr(args), "kwargs": repr(kwargs)}}) + "\\n")


def complete(*args, **kwargs):
    _record("complete", args, kwargs)
    raise RuntimeError("model call attempted during a docs-site render")


def __getattr__(name):
    def _any(*args, **kwargs):
        _record(name, args, kwargs)
        raise RuntimeError("model call attempted during a docs-site render")
    return _any
'''


@pytest.fixture
def guards(tmp_path, monkeypatch):
    """Block and record every network and model-provider subprocess call."""
    network_attempts = []
    model_proc_attempts = []

    def _deny(kind):
        def _blocked(*args, **kwargs):
            network_attempts.append((kind, repr(args)))
            raise OSError(f"network access blocked by test ({kind})")
        return _blocked

    monkeypatch.setattr(socket.socket, "connect", _deny("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", _deny("socket.connect_ex"))
    monkeypatch.setattr(socket.socket, "sendto", _deny("socket.sendto"))
    monkeypatch.setattr(socket, "create_connection", _deny("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", _deny("getaddrinfo"))
    monkeypatch.setattr(socket, "gethostbyname", _deny("gethostbyname"))

    real_popen = subprocess.Popen
    model_words = ("claude", "ollama", "anthropic", "openai", "gemini", "llm")

    class _GuardedPopen(real_popen):
        def __init__(self, args, *a, **kw):
            text = args if isinstance(args, str) else " ".join(map(str, args))
            if any(w in text.lower() for w in model_words):
                model_proc_attempts.append(text)
                raise OSError("model-provider subprocess blocked by test")
            super().__init__(args, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", _GuardedPopen)

    # Provider credentials removed so no SDK could even authenticate.
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    return network_attempts, model_proc_attempts


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph = _graph_dict()
    graph["edges"] = _sorted_edges(graph["edges"])
    (repo_root / "verification" / "corpus-graph.json").write_bytes(
        (json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode(
            "utf-8"
        )
    )
    log = tmp_path / "llm_calls.log"
    fake_dir = repo_root / "gen" / "llm-endpoint"
    fake_dir.mkdir(parents=True)
    (fake_dir / "llm_endpoint.py").write_text(
        _FAKE_LLM_ENDPOINT.format(log=str(log)), encoding="utf-8"
    )
    return repo_root, log


def _rendered_files(out_dir):
    return [p for p in Path(out_dir).rglob("*") if p.is_file()]


def _read_log(log):
    if not log.exists():
        return []
    return [line for line in log.read_text(encoding="utf-8").splitlines() if line]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_library_render_makes_no_network_or_model_call(tmp_path, guards):
    network_attempts, model_proc_attempts = guards
    _repo_root, log = _make_repo(tmp_path)

    raw = _graph_dict()
    graph = _Graph(
        nodes=raw["nodes"],
        edges=_sorted_edges(raw["edges"]),
        aggregates=raw["aggregates"],
    )
    out_dir = tmp_path / "site-lib"

    result = docs_site_renderer.render_docs_site(graph, out_dir)

    assert result is None
    assert _rendered_files(out_dir), "render produced no output files"
    assert network_attempts == [], f"network calls attempted: {network_attempts}"
    assert model_proc_attempts == [], (
        f"model-provider subprocesses attempted: {model_proc_attempts}"
    )
    assert _read_log(log) == [], f"model calls attempted: {_read_log(log)}"


def test_cli_render_makes_no_network_or_model_call(tmp_path, guards, monkeypatch):
    network_attempts, model_proc_attempts = guards
    repo_root, log = _make_repo(tmp_path)
    out_dir = tmp_path / "site-cli"
    monkeypatch.chdir(repo_root)

    cli = importlib.import_module("docs_site_renderer.cli")
    code = cli.main([f"--repo-root={repo_root}", f"--out={out_dir}"])

    assert code == 0
    assert _rendered_files(out_dir), "render produced no output files"
    assert network_attempts == [], f"network calls attempted: {network_attempts}"
    assert model_proc_attempts == [], (
        f"model-provider subprocesses attempted: {model_proc_attempts}"
    )
    assert _read_log(log) == [], f"model calls attempted: {_read_log(log)}"