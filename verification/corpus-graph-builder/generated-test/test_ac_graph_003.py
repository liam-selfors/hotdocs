import json
import tempfile
from pathlib import Path

import corpus_graph_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_component(repo_root, slug, title, sealed, extra_body=""):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    sealed_literal = "true" if sealed else "false"
    frontmatter = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        f"sealed: {sealed_literal}\n"
    )
    if sealed:
        frontmatter += f"source_path: legacy/{slug}/\n"
    frontmatter += "---\n\n"
    body = extra_body if extra_body else f"Purpose text for comp-{slug}.\n"
    (comp_dir / "component.md").write_text(frontmatter + body, encoding="utf-8")


def test_component_nodes_carry_verification_provenance_size_sealed_overrides():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        _write_component(repo_root, "a", "Comp A", sealed=True)
        _write_component(repo_root, "b", "Comp B", sealed=False)
        big_body = " ".join(["word"] * 4001) + "\n"
        _write_component(repo_root, "big", "Comp Big", sealed=True, extra_body=big_body)

        overrides_dir = repo_root / "gen" / "a"
        overrides_dir.mkdir(parents=True, exist_ok=True)
        (overrides_dir / ".overrides.json").write_text(
            json.dumps(["x.py"]), encoding="utf-8"
        )

        provenance_dir = repo_root / "verification" / "a"
        provenance_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "spec_bundle_hash": "sha256:abc",
            "generated_at": "2026-11-08T00:19:53Z",
            "verification_report": {"component_id": "comp-a", "overall": "pass"},
        }
        (provenance_dir / ".provenance.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        graph = corpus_graph_builder.build_corpus_graph(repo_root)

        graph_dict = graph.to_dict()
        nodes = _get(graph_dict, "nodes")

        comp_a = nodes["comp-a"]
        assert _get(comp_a, "verification") == {
            "component_id": "comp-a",
            "overall": "pass",
        }
        assert _get(comp_a, "provenance") == {
            "spec_bundle_hash": "sha256:abc",
            "generated_at": "2026-11-08T00:19:53Z",
        }
        assert _get(comp_a, "size_status") == "ok"
        assert _get(comp_a, "sealed") is True
        assert _get(comp_a, "pinned_overrides") == ["x.py"]

        comp_b = nodes["comp-b"]
        assert _get(comp_b, "verification") is None
        assert _get(comp_b, "provenance") is None
        assert _get(comp_b, "sealed") is False
        assert _get(comp_b, "pinned_overrides") == []

        comp_big = nodes["comp-big"]
        assert _get(comp_big, "size_status") == "over"

        raw_bytes = graph.to_json_bytes()
        assert isinstance(raw_bytes, bytes)
        json.loads(raw_bytes.decode("utf-8"))