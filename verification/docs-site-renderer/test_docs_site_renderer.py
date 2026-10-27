"""One test per AC-DOCS-* criterion in
specs/components/docs-site-renderer/acceptance/."""

import subprocess

from conftest import REPO_ROOT, SAMPLE_GRAPH
from docs_site_renderer import render_docs_site


def test_ac_docs_001_dag_contains_every_node_and_edge(out_dir):
    render_docs_site(SAMPLE_GRAPH, out_dir)
    index_html = (out_dir / "index.html").read_text(encoding="utf-8")
    for node_id in SAMPLE_GRAPH["nodes"]:
        assert node_id in index_html
    assert index_html.count('class="node-row"') == len(SAMPLE_GRAPH["nodes"])
    assert index_html.count('class="edge-row"') == len(SAMPLE_GRAPH["edges"])


def test_ac_docs_002_detail_view_includes_every_field(out_dir):
    render_docs_site(SAMPLE_GRAPH, out_dir)
    detail_files = list((out_dir / "nodes").glob("*comp-foo*"))
    assert len(detail_files) == 1
    detail_html = detail_files[0].read_text(encoding="utf-8")

    assert "R-FOO-001" in detail_html  # R-id list
    assert "AC-FOO-001" in detail_html  # acceptance criteria by kind
    assert "claude-sonnet-5" in detail_html  # provenance: model pin
    assert "v3" in detail_html  # provenance: prompt version
    assert "ok" in detail_html  # size status
    assert "Sealed" in detail_html  # sealed status
    assert "pipeline-team" in detail_html  # owners
    # D9's exclusion list: the verification-toggle item must not appear,
    # even though it was present in the input node's own owners list.
    assert "cross_model_divergence_check" not in detail_html


def test_ac_docs_003_dashboard_displays_exact_aggregate_values(out_dir):
    render_docs_site(SAMPLE_GRAPH, out_dir)
    health_html = (out_dir / "health.html").read_text(encoding="utf-8")
    assert "orphan_capability_rate" in health_html
    assert "0.25" in health_html
    assert "orphan_component_rate" in health_html


def test_ac_docs_004_pure_function_of_the_graph_alone(out_dir):
    # No repo filesystem at all -- a bare dict, matching interface/data's
    # own CorpusGraph.md shape, is the only input.
    render_docs_site(dict(SAMPLE_GRAPH), out_dir)
    assert (out_dir / "index.html").is_file()


def test_ac_docs_005_output_directory_is_gitignored(out_dir):
    render_docs_site(SAMPLE_GRAPH, out_dir)
    default_path = REPO_ROOT / "dist" / "docs-site" / "index.html"
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(default_path)],
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0  # 0 means git WOULD ignore this path


def test_ac_docs_006_no_network_or_model_call(out_dir, monkeypatch):
    import socket

    def _forbidden(*args, **kwargs):
        raise AssertionError("docs-site-renderer must never open a socket")

    monkeypatch.setattr(socket, "socket", _forbidden)
    render_docs_site(SAMPLE_GRAPH, out_dir)  # must not raise
    assert (out_dir / "index.html").is_file()
