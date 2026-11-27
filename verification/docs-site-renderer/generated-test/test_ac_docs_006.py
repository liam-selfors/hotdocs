# hotdocs-criterion: sha256:4f461e3da12630f4b732aa23791c46b060c793f068fef697dec2c29a2fdd0720
"""AC-DOCS-006: a render run makes no network call and no model call.

Covers R-DOCS-006: the docs-site renderer MUST make no model calls; it is a
pure rendering step.
"""

import importlib
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

import docs_site_renderer


MODEL_OR_NETWORK_PROGRAMS = ("claude", "ollama", "curl", "wget", "gemini", "openai")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _get_main():
    main = getattr(docs_site_renderer, "main", None)
    if main is None:
        cli = importlib.import_module("docs_site_renderer.cli")
        main = cli.main
    return main


def _corpus_graph():
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
                    "component.md": (
                        "---\nid: comp-foo\ntitle: Foo\nstatus: draft\n"
                        "owners: [pipeline-team]\ndepends_on: [comp-bar]\n"
                        "realizes: []\nuses_var: [VAR-FOO-URL]\nsealed: true\n"
                        "source_path: legacy/foo/\n---\n\n# Foo\n\nThe foo component.\n"
                    ),
                    "requirements/R-FOO-001.md": (
                        "# R-FOO-001\n\n**R-FOO-001** \u2014 MUST foo.\n"
                    ),
                    "acceptance/AC-FOO-001.md": (
                        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n"
                    ),
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
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 1.0,
            "orphan_component_rate": 0.5,
            "orphan_var_rate": 0.0,
        },
    }


def _write_fake_llm_endpoint(repo_root, log_path):
    base = repo_root / "gen" / "llm-endpoint"
    base.mkdir(parents=True, exist_ok=True)
    source = (
        "def _log(name):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
        "def complete(*args, **kwargs):\n"
        "    _log('complete')\n"
        "    raise RuntimeError('model call attempted during a render run')\n"
    )
    (base / "llm_endpoint.py").write_text(source, encoding="utf-8")


def test_ac_docs_006_render_run_makes_no_network_or_model_call(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph_path.write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "site"
    model_log = tmp_path / "model-calls.log"
    _write_fake_llm_endpoint(repo_root, model_log)

    # Credentials present, so any attempted model call would actually try to go out.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.chdir(repo_root)

    network_attempts = []
    subprocess_attempts = []

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_popen_init = subprocess.Popen.__init__

    def _is_inet(sock):
        try:
            return sock.family in (socket.AF_INET, socket.AF_INET6)
        except Exception:
            return True

    def guarded_connect(self, address, *args, **kwargs):
        if _is_inet(self):
            network_attempts.append(("connect", repr(address)))
            raise OSError("network call attempted during a render run: " + repr(address))
        return real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):
        if _is_inet(self):
            network_attempts.append(("connect_ex", repr(address)))
            raise OSError("network call attempted during a render run: " + repr(address))
        return real_connect_ex(self, address, *args, **kwargs)

    def guarded_create_connection(address, *args, **kwargs):
        network_attempts.append(("create_connection", repr(address)))
        raise OSError("network call attempted during a render run: " + repr(address))

    def guarded_getaddrinfo(host, *args, **kwargs):
        network_attempts.append(("getaddrinfo", repr(host)))
        raise OSError("name lookup attempted during a render run: " + repr(host))

    def guarded_popen_init(self, args, *rest, **kwargs):
        if isinstance(args, (str, bytes)):
            words = [args.decode() if isinstance(args, bytes) else args]
        else:
            words = [os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a) for a in args]
        joined = " ".join(words).lower()
        first = Path(words[0].split()[0]).name.lower() if words and words[0].split() else ""
        if any(p in first for p in MODEL_OR_NETWORK_PROGRAMS) or any(
            (" " + p + " ") in (" " + joined + " ") for p in MODEL_OR_NETWORK_PROGRAMS
        ):
            subprocess_attempts.append(joined)
            raise OSError("model/network subprocess attempted during a render run: " + joined)
        return real_popen_init(self, args, *rest, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(subprocess.Popen, "__init__", guarded_popen_init)

    main = _get_main()
    rc = main(["--repo-root=" + str(repo_root), "--out=" + str(out_dir)])

    assert network_attempts == [], "render run attempted network calls: " + repr(network_attempts)
    assert subprocess_attempts == [], (
        "render run attempted model/network subprocesses: " + repr(subprocess_attempts)
    )
    model_calls = model_log.read_text(encoding="utf-8").splitlines() if model_log.exists() else []
    assert model_calls == [], "render run made model calls: " + repr(model_calls)

    assert rc == 0
    assert (out_dir / "index.html").is_file()