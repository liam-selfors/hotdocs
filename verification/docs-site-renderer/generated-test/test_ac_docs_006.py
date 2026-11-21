# hotdocs-criterion: sha256:a1aa07ff4d3a8642531990f080a63365e1787e5d3dc85f8df5c70dfde41b14e8
"""AC-DOCS-006: a render run makes no network call and no model call.

The test runs a full render through the component's CLI (`main`) on a
synthetic `verification/corpus-graph.json`. While it runs, every way out
to the network is blocked and recorded: socket connect, DNS lookup and
UDP sends. Any spawn of a model CLI is recorded too. A fake `llm-endpoint`
is placed under the temporary repo root. Its `complete` logs every call to
a file the test controls, so a model call through it would show up there.
"""

import json
import socket
import subprocess
from pathlib import Path

import pytest

import docs_site_renderer


MODEL_BINARIES = ("claude", "ollama", "openai", "gemini", "anthropic")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _graph_dict():
    return {
        "nodes": {
            "P-DEMO-CAP": {"type": "capability"},
            "comp-alpha": {
                "type": "component",
                "verification": {
                    "requirement_results": {"R-ALPHA-001": "pass"},
                    "criteria": [
                        {"id": "AC-ALPHA-001", "kind": "generated-test", "result": "pass"}
                    ],
                },
                "provenance": {
                    "generated_at": "2026-01-01T00:00:00Z",
                    "model": "anthropic:claude-sonnet-5",
                },
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "# Alpha\n\nSee https://example.com/should-not-be-fetched\n",
                    "requirements/R-ALPHA-001.md": "**R-ALPHA-001** - MUST do a thing.\n",
                },
            },
            "comp-beta": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": [],
                "documents": {"component.md": "# Beta\n"},
            },
            "VAR-DEMO-URL": {"type": "var"},
        },
        "edges": [
            {"from": "comp-alpha", "to": "P-DEMO-CAP", "kind": "realizes"},
            {"from": "comp-alpha", "to": "VAR-DEMO-URL", "kind": "uses_var"},
            {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _write_fake_llm_endpoint(repo_root, log_path):
    target = repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(name):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
        "_log('import')\n"
        "\n"
        "def complete(*args, **kwargs):\n"
        "    _log('complete')\n"
        "    raise RuntimeError('model call made during docs-site render')\n"
    )
    target.write_text(source, encoding="utf-8")


def _install_guards(monkeypatch, attempts):
    def blocked(kind):
        def _raise(*args, **kwargs):
            attempts.append((kind, repr(args)[:200]))
            raise OSError("network access blocked by test: " + kind)

        return _raise

    monkeypatch.setattr(socket.socket, "connect", blocked("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocked("socket.connect_ex"))
    monkeypatch.setattr(socket.socket, "sendto", blocked("socket.sendto"))
    monkeypatch.setattr(socket, "create_connection", blocked("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", blocked("socket.getaddrinfo"))
    monkeypatch.setattr(socket, "gethostbyname", blocked("socket.gethostbyname"))

    real_popen_init = subprocess.Popen.__init__

    def guarded_popen_init(self, args, *rest, **kwargs):
        if isinstance(args, (list, tuple)):
            words = [str(a) for a in args]
        else:
            words = str(args).split()
        if words:
            exe = Path(words[0]).name.lower()
            if any(exe.startswith(b) for b in MODEL_BINARIES):
                attempts.append(("model-subprocess", repr(words)[:200]))
                raise OSError("model CLI spawn blocked by test")
        return real_popen_init(self, args, *rest, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", guarded_popen_init)


def test_ac_docs_006_render_run_makes_no_network_or_model_call(tmp_path, monkeypatch):
    repo_root = (tmp_path / "repo").resolve()
    (repo_root / "verification").mkdir(parents=True)
    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph_path.write_text(
        json.dumps(_graph_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    log_path = tmp_path / "llm_calls.log"
    _write_fake_llm_endpoint(repo_root, log_path)

    out_dir = tmp_path / "site-out"

    # Bogus credentials: no real model could be reached even if one were tried.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-invalid-key")
    monkeypatch.chdir(tmp_path)

    attempts = []
    _install_guards(monkeypatch, attempts)

    from docs_site_renderer import cli

    code = cli.main(["--repo-root=" + str(repo_root), "--out=" + str(out_dir)])

    monkeypatch.undo()

    assert code == 0, "render run did not succeed; exit code " + repr(code)
    assert (out_dir / "index.html").is_file(), "render produced no index.html"

    assert attempts == [], "network or model access attempted during render: " + repr(attempts)

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert "complete" not in calls, "llm-endpoint.complete was called during render: " + repr(calls)